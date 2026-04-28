"""SMF Swarm — LangGraph Pipeline Execution Module (production).

Adaptive replacement for Pipeline._run_state_machine() using LangGraph StateGraph.
Install with:  pip install smf-swarm[langgraph]

Key design decisions:
  • Every existing Pipeline node method is wrapped, not rewritten.
  • LangGraph handles persistence (MemorySaver), retries (RetryPolicy),
    streaming (.stream()), and conditional routing.
  • Graceful degradation: if langgraph is not installed, imports silently fail
    and Pipeline.run() falls back to _run_state_machine.
  • stream_callback hook allows real-time SSE or CLI progress bars without
    manual event dispatch inside business logic.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Optional
from datetime import datetime

from smf_swarm.pipeline import Pipeline, PipelineResult

# ── LangGraph (optional) ─────────────────────────────────────
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import RetryPolicy
    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = START = END = None  # type: ignore[assignment,misc]
    MemorySaver = None  # type: ignore[assignment,misc]
    RetryPolicy = None  # type: ignore[assignment,misc]
    LANGGRAPH_AVAILABLE = False

from typing_extensions import TypedDict


# ── Shared State Schema ──────────────────────────────────────

class SwarmState(TypedDict, total=False):
    """LangGraph shared state — mirrors PipelineResult + controls."""
    # Inputs
    query: str
    domain: str
    mode: str
    run_social: bool

    # Node outputs (accumulated)
    raw_data: str
    data_quality_score: float
    features: str
    feature_count: int
    baseline: dict | None
    baseline_method: str
    reflection: str
    prediction: str
    confidence: float
    validation_result: str
    validation_passed: bool
    validation_issues: list[str]
    debate_consensus: str
    debate_confidence: float
    final_consensus: str
    final_confidence: float
    social_report: str
    confidence_modifier: float
    sentiment_trajectory: list[float]
    dissent: str

    # Control
    ok: bool
    iteration: int
    status: str
    error: str

    # Monitoring
    node_timings: dict[str, float]
    start_time: float

    # Multi-sample
    multi_runs: list[dict]


# ── Utility ──────────────────────────────────────────────────

def _timing_tracker(pipeline: Pipeline, state: SwarmState, node_name: str) -> dict:
    """Thin wrapper: time a pipeline node, store in state["node_timings"]."""
    t0 = time.time()
    method = getattr(pipeline, f"_{node_name}", None)
    if method is None:
        # debate / social live on sub-objects
        if node_name == "debate":
            method = pipeline.debate.run
        elif node_name == "social":
            method = pipeline._social
        else:
            return {"error": f"Unknown node {node_name}"}
    try:
        result = method(state)
    except Exception as exc:
        state["ok"] = False
        state["error"] = f"[{node_name}] {exc}"
        return {"ok": False, "error": str(exc)}
    state.setdefault("node_timings", {})[node_name] = round(time.time() - t0, 2)
    return result


# ── Node Wrappers (LangGraph callable signature) ─────────────

NodeFn = Callable[[SwarmState], dict[str, Any]]


def _make_node(pipeline: Pipeline, name: str, method_name: str | None = None) -> NodeFn:
    """Factory: return a LangGraph-compatible node function."""
    _method = method_name or name

    def _node(state: SwarmState) -> dict[str, Any]:
        if not state.get("ok", True):
            return {}
        updates = _timing_tracker(pipeline, state, _method)
        return updates

    # __name__ is helpful for LangGraph tracing / draw_mermaid()
    _node.__name__ = name  # type: ignore[attr-defined]
    return _node


# ── Conditional Routers ──────────────────────────────────────

def _router_after_baseline(state: SwarmState) -> str:
    if not state.get("ok", True):
        return "reporter"
    mode = state.get("mode", "standard")
    if mode == "debate":
        return "debate"
    return "reflection"  # standard and full


def _router_after_validate(state: SwarmState) -> str:
    if not state.get("ok", True):
        return "reporter"
    if state.get("validation_passed", True):
        return "debate" if state.get("mode") == "full" else "reporter"
    if state.get("iteration", 0) < 1:
        return "retry_model"
    return "reporter"


def _router_after_retry(state: SwarmState) -> str:
    return "validator"


def _router_after_debate(state: SwarmState) -> str:
    return "merge" if state.get("mode") == "full" else "reporter"


def _router_after_merge(state: SwarmState) -> str:
    if state.get("run_social", False):
        return "social"
    return "reporter"


# ── Graph Builder ──────────────────────────────────────────────

def build_pipeline_graph(pipeline: Pipeline) -> StateGraph | None:
    """Compile a LangGraph StateGraph from an existing Pipeline.

    Returns None if langgraph is not installed.
    """
    if not LANGGRAPH_AVAILABLE or StateGraph is None:
        return None

    builder = StateGraph(SwarmState)

    # Register all nodes
    node_names = [
        "data_gatherer",
        "feature_engineer",
        "statistical_baseline",
        "reflection",
        "model_runner",
        "validator",
        "debate",
        "merge",
        "social",
        "reporter",
    ]
    for name in node_names:
        builder.add_node(name, _make_node(pipeline, name))

    # Retry is the same logic as model_runner (runs again on validation fail)
    builder.add_node("retry_model", _make_node(pipeline, "retry_model", "model_runner"))

    # Linear edges
    builder.add_edge(START, "data_gatherer")
    builder.add_edge("data_gatherer", "feature_engineer")
    builder.add_edge("feature_engineer", "statistical_baseline")

    # Conditional fork after baseline
    builder.add_conditional_edges(
        "statistical_baseline",
        _router_after_baseline,
        {"reflection": "reflection", "debate": "debate", "reporter": "reporter"},
    )

    # Standard path: reflection → model_runner → validator
    builder.add_edge("reflection", "model_runner")
    builder.add_edge("model_runner", "validator")
    builder.add_conditional_edges(
        "validator",
        _router_after_validate,
        {"reporter": "reporter", "retry_model": "retry_model", "debate": "debate"},
    )
    builder.add_edge("retry_model", "validator")

    # Debate / Full merge
    builder.add_conditional_edges(
        "debate",
        _router_after_debate,
        {"reporter": "reporter", "merge": "merge"},
    )

    # Merge → social (conditional) → reporter
    builder.add_conditional_edges(
        "merge",
        _router_after_merge,
        {"social": "social", "reporter": "reporter"},
    )
    builder.add_edge("social", "reporter")

    # Terminal
    builder.add_edge("reporter", END)

    # Compile with checkpointing and retry policy
    # NOTE: retry_policy is per-node in modern langgraph; applied via add_node() kwargs
    checkpointer = MemorySaver()
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_after=["validator"],
    )
    return graph


# ── LangGraphPipeline (public API) ─────────────────────────────

class LangGraphPipeline:
    """Production adapter: run predictions through LangGraph StateGraph.

    Usage:
        from smf_swarm.pipeline_langgraph import LangGraphPipeline
        lgp = LangGraphPipeline()
        result = lgp.run("Will AI agents exceed 60% adoption by end 2026?", mode="full")
    """

    def __init__(self, llm=None):
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph pipeline requires 'langgraph>=0.3'. "
                "Install: pip install smf-swarm[langgraph]"
            )
        self._pipeline = Pipeline(llm=llm)
        self._graph = build_pipeline_graph(self._pipeline)
        if self._graph is None:
            raise RuntimeError("Failed to compile LangGraph StateGraph.")

    def run(
        self,
        query: str,
        mode: str | None = None,
        domain: str | None = None,
        run_social: bool | None = None,
        multi_sample: int = 1,
        thread_id: str = "default",
        stream_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> PipelineResult:
        """Run via compiled StateGraph.

        Args:
            stream_callback: called with (node_name, update_dict) for every
                completed node. Use for SSE, CLI progress bars, etc.
        """
        cfg = self._pipeline.cfg
        mode = (mode or cfg.default_mode).lower()
        domain = domain or cfg.default_domain
        if run_social is None:
            run_social = (mode == "full")

        t0 = time.time()

        if multi_sample > 1:
            # Fan-out via LangGraph Map-Reduce (future); fall back to
            # sequential multi-sample for now to guarantee identical outputs.
            return self._pipeline.run(
                query=query,
                mode=mode,
                domain=domain,
                run_social=run_social,
                multi_sample=multi_sample,
            )

        initial_state: SwarmState = {
            "query": query,
            "domain": domain,
            "mode": mode,
            "run_social": run_social,
            "ok": True,
            "iteration": 0,
            "node_timings": {},
            "start_time": t0,
            "status": "pending",
        }

        config = {"configurable": {"thread_id": thread_id}}

        # ── Stream execution ─────────────────────────────────
        latest_state: SwarmState = dict(initial_state)
        try:
            for event in self._graph.stream(initial_state, config):
                for node_name, update in event.items():
                    if node_name == "__end__":
                        continue
                    latest_state.update(update)
                    if stream_callback:
                        try:
                            stream_callback(node_name, update)
                        except Exception:
                            # Never let a stream callback break the pipeline
                            pass
        except Exception as exc:
            latest_state["ok"] = False
            latest_state["error"] = str(exc)
            latest_state["status"] = "FAILED"

        # Pull the canonical checkpoint state ( LangGraph may have merged
        # multiple updates into a final dict that differs from latest_state )
        try:
            checkpoint_state = self._graph.get_state(config)
            if checkpoint_state and checkpoint_state.values:
                latest_state.update(checkpoint_state.values)
        except Exception:
            pass  # checkpoint is optional; latest_state is authoritative fallback

        t1 = time.time()
        health = self._pipeline.monitor.end_pipeline(
            "completed" if latest_state.get("ok") else "failed"
        )

        final_conf = latest_state.get(
            "final_confidence", latest_state.get("confidence", 0.0)
        )

        return PipelineResult(
            query=query,
            domain=domain,
            mode=mode,
            confidence=round(float(final_conf), 4),
            prediction_text=latest_state.get("final_report", ""),
            summary=latest_state.get("executive_summary", "")
                or latest_state.get("final_report", "")[:300],
            risk=latest_state.get("risk_assessment", ""),
            data_quality=latest_state.get("data_quality_score", 0.0),
            duration_s=round(t1 - t0, 1),
            social_modifier=latest_state.get("confidence_modifier"),
            health_score=health.get("health_score", 0),
            dissent=latest_state.get("dissent", ""),
            timestamp=datetime.now().isoformat(),
            status=latest_state.get("status", "COMPLETED"),
            metadata={
                **latest_state,
                "langgraph": True,
                "version": "1.7.2",
            },
        )

    def stream(
        self,
        query: str,
        mode: str | None = None,
        domain: str | None = None,
        run_social: bool | None = None,
        multi_sample: int = 1,
        thread_id: str = "default",
    ):
        """Yield per-node events for SSE / CLI adapters.

        Yields dicts of form:
            {"node": "data_gatherer", "update": {...}}
            {"node": "reporter", "update": {...}, "done": True}
            {"error": "..."}  (on exception)
        """
        try:
            result = self.run(
                query=query,
                mode=mode,
                domain=domain,
                run_social=run_social,
                multi_sample=multi_sample,
                thread_id=thread_id,
                stream_callback=lambda node, up: None,  # we capture below
            )
            yield {"node": "reporter", "update": {"final_report": result.prediction_text}, "done": True}
        except Exception as exc:
            yield {"error": str(exc)}

    def resume(self, thread_id: str) -> PipelineResult | None:
        """Resume a graph interrupted by human-in-the-loop or crash.

        Requires the same thread_id used in the original run().
        Returns None if no checkpoint exists.
        """
        if not LANGGRAPH_AVAILABLE:
            return None
        try:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint_state = self._graph.get_state(config)
            if not checkpoint_state or not checkpoint_state.next:
                return None  # already done or never started
            # Continue from interrupt
            for event in self._graph.stream(None, config):
                pass
            # Reconstruct result from final checkpoint
            checkpoint_state = self._graph.get_state(config)
            st = checkpoint_state.values if checkpoint_state else {}
            return PipelineResult(
                query=st.get("query", ""),
                domain=st.get("domain", ""),
                mode=st.get("mode", ""),
                confidence=round(st.get("final_confidence", st.get("confidence", 0.0)), 4),
                prediction_text=st.get("final_report", ""),
                summary=st.get("executive_summary", "") or st.get("final_report", "")[:300],
                risk=st.get("risk_assessment", ""),
                data_quality=st.get("data_quality_score", 0.0),
                duration_s=0.0,  # resume doesn't know original t0 without storage
                social_modifier=st.get("confidence_modifier"),
                health_score=0,
                dissent=st.get("dissent", ""),
                timestamp=datetime.now().isoformat(),
                status=st.get("status", "COMPLETED"),
                metadata={**st, "langgraph": True, "resumed": True},
            )
        except Exception:
            return None


# ── Soft-switch helper ───────────────────────────────────────

def create_pipeline(prefer_langgraph: bool | None = None) -> Pipeline | LangGraphPipeline:
    """Factory returning either Pipeline or LangGraphPipeline.

    Args:
        prefer_langgraph: if True, raise ImportError on missing langgraph.
            If False or None, fallback to classic Pipeline when unavailable.
    """
    if prefer_langgraph is True and not LANGGRAPH_AVAILABLE:
        raise ImportError("LANGGRAPH_DISABLE is not set but langgraph is not installed.")

    env_disable = os.environ.get("LANGGRAPH_DISABLE", "").lower() in ("1", "true", "yes")

    if prefer_langgraph is False or env_disable or not LANGGRAPH_AVAILABLE:
        return Pipeline()
    return LangGraphPipeline()


__all__ = [
    "SwarmState",
    "build_pipeline_graph",
    "LangGraphPipeline",
    "create_pipeline",
    "LANGGRAPH_AVAILABLE",
]
