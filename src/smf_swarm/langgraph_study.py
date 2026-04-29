"""SMF Swarm — LangGraph Migration Feasibility Study

DEPRECATED: This module was the original prototype. The production module is
`pipeline_langgraph.py`. This file is kept for reference only.
"""

from __future__ import annotations

import time
from typing_extensions import TypedDict
from smf_swarm.pipeline import Pipeline, PipelineResult

# ── LangGraph imports (optional; module gracefully degrades) ──
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import RetryPolicy

    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = START = END = None  # type: ignore
    MemorySaver = None  # type: ignore
    RetryPolicy = None  # type: ignore
    LANGGRAPH_AVAILABLE = False


# ── Shared State Schema ────────────────────────────────────────


# Note: LangGraph state must be TypedDict or dataclass. We mirror PipelineResult
# fields plus per-node mutable tracking.
class SwarmState(TypedDict, total=False):
    """LangGraph shared-state definition.

    Every node receives the current SwarmState dict and must return a dict
    of key/value updates (LangGraph merges with the latest state).
    """

    # Input / config
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

    # Control / routing
    ok: bool
    iteration: int
    status: str
    error: str

    # Monitoring
    node_timings: dict[str, float]
    start_time: float

    # Multi-sample
    multi_runs: list[dict]


# ─── Node Wrappers (thin adapters) ────────────────────────────

# Each wrapper takes a Pipeline instance + state and returns updates.
# The underlying logic stays in pipeline.py unchanged.


def _node_data_gatherer(pipeline: "Pipeline", state: SwarmState) -> dict:
    """LangGraph node wrapper for _data_gatherer."""
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._data_gatherer(state)
    state["node_timings"]["data_gatherer"] = time.time() - t0
    return result


def _node_feature_engineer(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._feature_engineer(state)
    state["node_timings"]["feature_engineer"] = time.time() - t0
    return result


def _node_statistical_baseline(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._statistical_baseline(state)
    state["node_timings"]["statistical_baseline"] = time.time() - t0
    return result


def _node_reflection(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._reflection(state)
    state["node_timings"]["reflection"] = time.time() - t0
    return result


def _node_model_runner(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._model_runner(state)
    state["node_timings"]["model_runner"] = time.time() - t0
    return result


def _node_validator(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._validator(state)
    state["node_timings"]["validator"] = time.time() - t0
    # Conditional routing will read state["validation_passed"]
    return result


def _node_debate(pipeline: "Pipeline", state: SwarmState) -> dict:
    """LangGraph node wrapper for DebateEngine.run()"""
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    deb_state = pipeline.debate.run(
        {
            "query": state["query"],
            "domain": state["domain"],
            "features": state.get("features", ""),
            "data_quality": state.get("data_quality_score", 0.5),
        }
    )
    state["node_timings"]["debate"] = time.time() - t0
    return deb_state


def _node_merge(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._merge(state)
    state["node_timings"]["merge"] = time.time() - t0
    return result


def _node_social(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._social(state)
    state["node_timings"]["social"] = time.time() - t0
    return result


def _node_reporter(pipeline: "Pipeline", state: SwarmState) -> dict:
    if not state.get("ok", True):
        return {}
    t0 = time.time()
    result = pipeline._reporter(state)
    state["node_timings"]["reporter"] = time.time() - t0
    return result


# ─── Conditional Routers ─────────────────────────────────────

# LangGraph conditional edges return a string that maps to a node name.
# These functions inspect state and decide the next destination.


def _router_after_baseline(state: SwarmState) -> str:
    """After baseline, route into the mode-specific sub-graph."""
    mode = state.get("mode", "standard")
    if not state.get("ok", True):
        return "reporter"  # fail fast to reporter with error context
    if mode == "standard":
        return "reflection"
    if mode == "debate":
        return "debate"
    return "reflection"  # full mode starts standard sub-path


def _router_after_validate(state: SwarmState) -> str:
    """After validator: retry once on failure, otherwise continue."""
    if not state.get("ok", True):
        return "reporter"
    if state.get("validation_passed", True):
        mode = state.get("mode", "standard")
        if mode == "full":
            return "debate"
        return "reporter"
    # Retry path (one extra attempt, matching existing logic)
    if state.get("iteration", 0) < 1:
        return "retry_model"
    return "reporter"


def _router_after_retry(state: SwarmState) -> str:
    """After retry model run, always jump back to validator."""
    return "validator"


def _router_after_debate(state: SwarmState) -> str:
    """After debate: standard debate goes to reporter; full goes to merge."""
    mode = state.get("mode", "debate")
    if mode == "debate":
        return "reporter"
    return "merge"


def _router_after_merge(state: SwarmState) -> str:
    """After merge: conditional social simulation then reporter."""
    if state.get("run_social", False):
        return "social"
    return "reporter"


# ─── Graph Assembler ──────────────────────────────────────────


def build_pipeline_graph(pipeline: "Pipeline") -> StateGraph | None:
    """Build and compile a LangGraph StateGraph from an existing Pipeline.

    Returns None if LangGraph is not installed (graceful degradation).
    """
    if not LANGGRAPH_AVAILABLE:
        return None

    builder = StateGraph(SwarmState)

    # ── Register nodes (partial = pre-bind Pipeline instance) ──
    builder.add_node("data_gatherer", lambda s: _node_data_gatherer(pipeline, s))
    builder.add_node("feature_engineer", lambda s: _node_feature_engineer(pipeline, s))
    builder.add_node(
        "statistical_baseline", lambda s: _node_statistical_baseline(pipeline, s)
    )
    builder.add_node("reflection", lambda s: _node_reflection(pipeline, s))
    builder.add_node("model_runner", lambda s: _node_model_runner(pipeline, s))
    builder.add_node("validator", lambda s: _node_validator(pipeline, s))
    builder.add_node(
        "retry_model", lambda s: _node_model_runner(pipeline, s)
    )  # same logic, re-run
    builder.add_node("debate", lambda s: _node_debate(pipeline, s))
    builder.add_node("merge", lambda s: _node_merge(pipeline, s))
    builder.add_node("social", lambda s: _node_social(pipeline, s))
    builder.add_node("reporter", lambda s: _node_reporter(pipeline, s))

    # ── Linear edges ──
    builder.add_edge(START, "data_gatherer")
    builder.add_edge("data_gatherer", "feature_engineer")
    builder.add_edge("feature_engineer", "statistical_baseline")

    # ── Conditional fork after baseline ──
    builder.add_conditional_edges(
        "statistical_baseline",
        _router_after_baseline,
        {
            "reflection": "reflection",
            "debate": "debate",
            "reporter": "reporter",
        },
    )

    # ── Standard path ──
    builder.add_edge("reflection", "model_runner")
    builder.add_edge("model_runner", "validator")
    builder.add_conditional_edges(
        "validator",
        _router_after_validate,
        {
            "reporter": "reporter",
            "retry_model": "retry_model",
            "debate": "debate",
        },
    )
    builder.add_edge("retry_model", "validator")

    # ── Debate / Full merge ──
    builder.add_conditional_edges(
        "debate",
        _router_after_debate,
        {
            "reporter": "reporter",
            "merge": "merge",
        },
    )

    # ── Full merge → social → reporter ──
    builder.add_conditional_edges(
        "merge",
        _router_after_merge,
        {
            "social": "social",
            "reporter": "reporter",
        },
    )
    builder.add_edge("social", "reporter")

    # ── Terminal ──
    builder.add_edge("reporter", END)

    # ── Compile with checkpointing ──
    checkpointer = MemorySaver()
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_after=["validator"],  # human-in-the-loop: approve before continuing
    )
    return graph


# ─── LangGraphPipeline (public API, experimental) ───────────────


class LangGraphPipeline:
    """Experimental replacement for Pipeline.run() using LangGraph.

    Usage:
        from smf_swarm.langgraph_study import LangGraphPipeline
        lgp = LangGraphPipeline()
        result = lgp.run("...", mode="full")
    """

    def __init__(self, llm=None):
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph migration requires 'langgraph>=0.3'. "
                "Install: pip install smf-swarm[langgraph]"
            )
        self._pipeline = Pipeline(llm=llm)
        self._graph = build_pipeline_graph(self._pipeline)
        if self._graph is None:
            raise RuntimeError("Failed to compile LangGraph.")

    def run(
        self,
        query: str,
        mode: str = None,
        domain: str = None,
        run_social: bool = None,
        multi_sample: int = 1,
        thread_id: str = "default",
    ) -> PipelineResult:
        """Run via compiled StateGraph with persistence and streaming."""
        from datetime import datetime

        cfg = self._pipeline.cfg
        mode = (mode or cfg.default_mode).lower()
        domain = domain or cfg.default_domain
        if run_social is None:
            run_social = mode == "full"

        t0 = time.time()

        if multi_sample > 1:
            # LangGraph natively supports Map-Reduce for fan-out;
            # here we fall back to the existing sequential multi-sample
            # implementation for compatibility.
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

        # Stream events node-by-node (perfect for SSE web UI)
        for event in self._graph.stream(initial_state, config):
            # event format: {"node_name": {"updated_key": value, ...}, ...}
            for node_name, update in event.items():
                if node_name == "__end__":
                    continue
                print(
                    f"[LangGraph] Node '{node_name}' complete → {list(update.keys())}"
                )

        # Final state after graph terminates
        final_state = self._graph.get_state(config).values

        t1 = time.time()
        health = self._pipeline.monitor.end_pipeline(
            "completed" if final_state.get("ok") else "failed"
        )

        return PipelineResult(
            query=query,
            domain=domain,
            mode=mode,
            confidence=round(
                final_state.get("final_confidence", final_state.get("confidence", 0.0)),
                4,
            ),
            prediction_text=final_state.get("final_report", ""),
            summary=final_state.get("executive_summary", "")
            or final_state.get("final_report", "")[:300],
            risk=final_state.get("risk_assessment", ""),
            data_quality=final_state.get("data_quality_score", 0.0),
            duration_s=round(t1 - t0, 1),
            social_modifier=final_state.get("confidence_modifier"),
            health_score=health.get("health_score", 0),
            dissent=final_state.get("dissent", ""),
            timestamp=datetime.now().isoformat(),
            status=final_state.get("status", "COMPLETED"),
            metadata={**final_state, "langgraph": True},
        )


# ─── Migration Effort & Risk Assessment ───────────────────────

"""
╔════════════════════════ MIGRATION EFFORT ══════════════════════════╗
║                                                                    ║
║  Phase 1: Wrapper scaffolding (this file)        → DONE (study)   ║
║  Phase 2: Add [langgraph] extra to pyproject.toml                  ║
║           + pip install langgraph>=0.3                            ║
║  Phase 3: Node-level unit tests (all 3 modes)                     ║
║  Phase 4: Web UI SSE adapter for .stream() events                 ║
║  Phase 5: Backtest store integration with checkpoint metadata       ║
║  Phase 6: A/B test: sequential vs. LangGraph on 20 runs         ║
║  Phase 7: Swap default Pipeline.run() → LangGraphPipeline         ║
║                                                                    ║
║  ESTIMATED EFFORT: 2–4 weeks (1 FTE)                              ║
║  RISK: Low — additive migration; fallback to _run_state_machine   ║
║         remains available via env var LANGGRAPH_DISABLE=1          ║
║                                                                    ║
╠════════════════════════ ADVANTAGES ═══════════════════════════════╣
║  • Persistence: crashes resume mid-pipeline (MemorySaver/SQLite)   ║
║  • Streaming: native .stream() replaces manual SSE event dispatch  ║
║  • Retries: per-node RetryPolicy (e.g., validator gets 2 tries)   ║
║  • Human-in-the-loop: interrupt_after validates for approval     ║
║  • Parallel branches: debate openings as fan-out (already done)   ║
║  • Visualization: draw_mermaid() generates graph diagrams        ║
║  • Observability: LangSmith tracing compatible                     ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
"""
