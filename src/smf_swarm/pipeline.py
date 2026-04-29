"""SMF Swarm — Core Pipeline.

Orchestrates three prediction modes:
  Standard:  gather → engineer → reflect → model → validate → report
  Debate:    gather → engineer → debate (3 agents × 2 rounds) → report
  Full:      standard + debate → merge → social validation → report

Usage:
    from smf_swarm import Pipeline
    p = Pipeline()
    result = p.run("Will AI agent adoption exceed 60% by end 2026?", mode="full", domain="technology")
    print(result.confidence, result.summary)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from smf_swarm.config import get_config, create_llm
from smf_swarm.debate.engine import DebateEngine
from smf_swarm.social.simulator import SocialSimulator
from smf_swarm.monitor import SwarmMonitor
from smf_swarm.structured import (
    extract_confidence,
    extract_data_quality,
    extract_feature_count,
    extract_validation,
    extract_report_sections,
)
from smf_swarm.backtest import BacktestStore
from smf_swarm.cache import LLMCache  # kept for backward compat; cache init below

# ── LangGraph soft-switch (optional) ──────────────────────────
_LANGGRAPH_PIPELINE = None
_LANGGRAPH_AVAILABLE = False
try:
    from smf_swarm.pipeline_langgraph import LangGraphPipeline

    _LANGGRAPH_PIPELINE = LangGraphPipeline
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    _LANGGRAPH_PIPELINE = None


# ─── Result objects ─────────────────────────────


@dataclass
class PipelineResult:
    """Structured output from any prediction run."""

    query: str
    domain: str
    mode: str
    confidence: float = 0.0
    prediction_text: str = ""
    summary: str = ""
    risk: str = ""
    data_quality: float = 0.0
    duration_s: float = 0.0
    social_modifier: Optional[float] = None
    health_score: float = 0.0
    dissent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
    metadata: dict = field(default_factory=dict)


# ─── Pipeline ─────────────────────────────────────


class Pipeline:
    """High-level interface for running predictions."""

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.cfg = get_config()
        self.llm = llm or create_llm(self.cfg.llm)
        self.debate = DebateEngine(self.llm)
        self.social = SocialSimulator(self.llm)
        self.monitor = SwarmMonitor()
        # Initialize LLM response cache

        self._cache = LLMCache()
        # Backtest store for calibration tracking
        self._backtest = BacktestStore()
        # Statistical baseline (optional [predict] extras)
        try:
            from smf_swarm.predict.baseline import StatisticalBaseline

            self._baseline: "StatisticalBaseline | None" = StatisticalBaseline()
        except Exception:
            self._baseline = None

    def run(
        self,
        query: str,
        mode: str = None,
        domain: str = None,
        run_social: bool = None,
        multi_sample: int = 1,
        langgraph: bool | None = None,
    ) -> PipelineResult:
        """Run a prediction in the specified mode.

        Args:
            multi_sample: Number of temperature-swept runs to average for
                uncertainty quantification (default 1 = single run).
            langgraph: If True (default when installed), use LangGraph backend.
                If False, force classic _run_state_machine.
                If None, auto-detect: use LangGraph when available.
                Environment LANGGRAPH_DISABLE=1 forces classic backend.
        """
        env_disable = os.environ.get("LANGGRAPH_DISABLE", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if env_disable or langgraph is False:
            use_langgraph = False
        elif langgraph is True:
            use_langgraph = True
        elif langgraph is None and _LANGGRAPH_AVAILABLE:
            use_langgraph = True  # DEFAULT: use LangGraph when installed
        else:
            use_langgraph = False

        if use_langgraph and _LANGGRAPH_AVAILABLE and _LANGGRAPH_PIPELINE is not None:
            lgp = _LANGGRAPH_PIPELINE(llm=self.llm)
            return lgp.run(
                query=query,
                mode=mode,
                domain=domain,
                run_social=run_social,
                multi_sample=multi_sample,
                thread_id=f"pipe_{id(self)}_{time.time()}",
            )

        mode = (mode or self.cfg.default_mode).lower()
        domain = domain or self.cfg.default_domain
        if run_social is None:
            run_social = mode == "full"

        t0 = time.time()
        self.monitor.reset()
        self.monitor.start_pipeline(query, mode)

        # Multi-sample support: run N times at varied temperatures
        if multi_sample > 1:
            results = self._multi_sample_run(
                query, mode, domain, run_social, n=multi_sample
            )
            state = results["aggregated_state"]
            multi_meta = results
        else:
            state = self._run_state_machine(query, mode, domain, run_social)
            multi_meta = {}

        health = self.monitor.end_pipeline("completed" if state.get("ok") else "failed")
        t1 = time.time()

        final_conf = state.get("final_confidence", 0.0)
        conf_std = multi_meta.get("confidence_std", 0.0)

        result = PipelineResult(
            query=query,
            domain=domain,
            mode=mode,
            confidence=round(final_conf, 4),
            prediction_text=state.get("final_report", ""),
            summary=state.get("executive_summary", ""),
            risk=state.get("risk_assessment", ""),
            data_quality=state.get("data_quality_score", 0.0),
            duration_s=round(t1 - t0, 1),
            social_modifier=state.get("confidence_modifier"),
            health_score=health.get("health_score", 0),
            dissent=state.get("dissent", ""),
            timestamp=datetime.now().isoformat(),
            status=state.get("status", "COMPLETED"),
            metadata={**state, "multi_sample": multi_meta},
        )

        # Record to backtest store
        try:
            self._backtest.record(
                query=query,
                domain=domain,
                mode=mode,
                prediction=result.summary,
                confidence=result.confidence,
                llm_model=self.cfg.llm.model,
                temperature=self.cfg.llm.temperature,
                social_agents=self.cfg.social_agents,
                social_rounds=self.cfg.social_rounds,
                duration_s=result.duration_s,
                data_quality=result.data_quality,
                health_score=result.health_score,
                social_modifier=result.social_modifier,
                langgraph=result.metadata.get("langgraph", False),
                thread_id=result.metadata.get("thread_id", ""),
            )
        except Exception:
            pass  # best-effort; never block on backtest

        return result

    def _multi_sample_run(
        self, query: str, mode: str, domain: str, run_social: bool, n: int
    ) -> dict:
        """Run pipeline n times at varied temperatures. Returns aggregated state."""
        import numpy as np

        # Temperature values: base ± small perturbations (bounded 0.1–0.9)
        base_temp = self.cfg.llm.temperature
        temps = [max(0.1, min(0.9, base_temp + (i - n // 2) * 0.15)) for i in range(n)]

        states = []
        confidences = []

        original_temperature = self.cfg.llm.temperature
        for i, temp in enumerate(temps):
            try:
                self.cfg.llm.temperature = temp
                st = self._run_state_machine(query, mode, domain, run_social)
                states.append(st)
                confidences.append(
                    st.get("final_confidence", st.get("confidence", 0.5))
                )
                print(
                    f"  [Multi-sample] Run {i + 1}/{n} temp={temp:.2f} conf={confidences[-1]:.2f}"
                )
            except Exception as e:
                print(f"  [Multi-sample] Run {i + 1}/{n} FAILED: {e}")
            finally:
                self.cfg.llm.temperature = original_temperature

        if not confidences:
            # Fallback to single run with base temp
            self.cfg.llm.temperature = original_temperature
            st = self._run_state_machine(query, mode, domain, run_social)
            return {
                "aggregated_state": st,
                "confidence_mean": st.get("final_confidence", 0.0),
                "confidence_std": 0.0,
                "temperatures": [original_temperature],
                "confidences": [st.get("final_confidence", 0.0)],
                "runs": 1,
            }

        mean_conf = float(np.mean(confidences))
        std_conf = float(np.std(confidences))
        # Use the state with confidence closest to mean as representative
        best_idx = int(np.argmin([abs(c - mean_conf) for c in confidences]))
        rep_state = dict(states[best_idx])
        rep_state["final_confidence"] = round(mean_conf, 4)

        return {
            "aggregated_state": rep_state,
            "confidence_mean": round(mean_conf, 4),
            "confidence_std": round(std_conf, 4),
            "temperatures": temps,
            "confidences": confidences,
            "runs": len(confidences),
        }

    def _cached_invoke(self, messages: list, node_name: str = "") -> Any:
        """Invoke LLM with disk-backed response caching."""
        kwargs = {"model": self.cfg.llm.model, "temperature": self.cfg.llm.temperature}
        cached = self._cache.get(messages, **kwargs)
        if cached:
            print(f"  [Cache] Hit for {node_name}")
            return cached
        resp = self.llm.invoke(messages)
        self._cache.set(messages, resp, **kwargs)
        return resp

    def _run_state_machine(
        self, query: str, mode: str, domain: str, run_social: bool
    ) -> dict:
        """Execute sequential node graph."""
        state: dict = {
            "query": query,
            "domain": domain,
            "mode": mode,
            "run_social": run_social,
            "ok": True,
        }
        try:
            # ── Gather ─────────────────────────
            state.update(self._data_gatherer(state))
            # ── Engineer ───────────────────────
            state.update(self._feature_engineer(state))
            # ── Statistical Baseline (optional) ──
            state.update(self._statistical_baseline(state))

            if mode in ("standard", "full"):
                # ── Reflect (Standard) ───────────
                state.update(self._reflection(state))
                # ── Model (Standard) ─────────────
                state.update(self._model_runner(state))
                # ── Validate ───────────────────
                state.update(self._validator(state))
                if not state.get("validation_passed", True):
                    state["iteration"] = state.get("iteration", 0) + 1
                    state.update(self._model_runner(state))
                    state.update(self._validator(state))

            if mode in ("debate", "full"):
                # ── Debate ───────────────────────
                deb_state = self.debate.run(
                    {
                        "query": query,
                        "domain": domain,
                        "features": state.get("features", ""),
                        "data_quality": state.get("data_quality_score", 0.5),
                    }
                )
                state.update(deb_state)

            if mode == "full":
                # ── Merge ────────────────────────
                state.update(self._merge(state))
                # ── Social ───────────────────────
                if run_social:
                    state.update(self._social(state))

            # ── Report ───────────────────────────
            state.update(self._reporter(state))

        except Exception as e:
            state["ok"] = False
            state["error"] = str(e)
            state["status"] = "FAILED"
            print(f"[Pipeline ERROR] {e}")

        return state

    # ── Node functions ───────────────────────────

    def _data_gatherer(self, state: dict) -> dict:
        with self.monitor.track("data_gatherer"):
            enriched = ""
            # Optional tool search
            try:
                from smf_swarm.tools import ToolKit

                toolkit = ToolKit()
                if toolkit.search_available:
                    search = toolkit.duckduckgo_search(state["query"], max_results=3)
                    if search.get("results"):
                        snippets = "\n".join(
                            f"- {r['title']}: {r['body'][:200]}"
                            for r in search["results"]
                        )
                        enriched = f"\n\n--- Web Search Snippets ---\n{snippets}\n"
            except Exception:
                pass
            # Optional RAG context
            rag_context = ""
            try:
                from smf_swarm.rag import RAGStore

                rag = RAGStore()
                if rag.available:
                    rag_results = rag.query(state["query"], n_results=3)
                    if rag_results.get("results"):
                        chunks = "\n".join(
                            f"- {r['text'][:200]}" for r in rag_results["results"]
                        )
                        rag_context = f"\n\n--- Uploaded Reports ---\n{chunks}\n"
            except Exception:
                pass
            ctx = (
                f"Gather data and signal sources for: {state['query']}\n"
                f"Domain: {state['domain']}\n"
                f"{enriched}{rag_context}\n"
                "List key data sources, historical precedents, current indicators.\n"
                "End with DATA_QUALITY_SCORE: [0-1]"
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "data_gatherer")
            quality = extract_data_quality(resp.content)
            return {"raw_data": resp.content, "data_quality_score": quality}

    def _feature_engineer(self, state: dict) -> dict:
        with self.monitor.track("feature_engineer"):
            ctx = (
                f"Engineer predictive features for: {state['query']}\n"
                f"Data: {state['raw_data'][:2000]}\n"
                "Identify top 5-8 predictive features.\n"
                "End with FEATURE_COUNT: [number]"
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "feature_engineer")
            count = extract_feature_count(resp.content)
            return {"features": resp.content, "feature_count": count}

    def _reflection(self, state: dict) -> dict:
        """Chain-of-thought reasoning extraction before prediction."""
        with self.monitor.track("reflection"):
            ctx = (
                f"QUERY: {state['query']}\n"
                f"FEATURES: {str(state['features'])[:2000]}\n\n"
                "BEFORE predicting, explicitly reason through:\n"
                "1. Base rate for this type of prediction?\n"
                "2. Strongest single piece of evidence?\n"
                "3. Most likely way you could be wrong?\n"
                "4. What would change your mind?\n\n"
                "Do NOT give the prediction. Give ONLY structured reasoning (max 500 words)."
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "reflection")
            return {"reflection": resp.content}

    def _model_runner(self, state: dict) -> dict:
        with self.monitor.track("model_runner"):
            refl = ""
            if state.get("reflection"):
                refl = f"\nREFLECTION:\n{state['reflection'][:800]}\n"
            ctx = (
                f"PREDICTION QUERY: {state['query']}\n"
                f"FEATURES: {str(state['features'])[:2000]}{refl}\n"
                f"DATA QUALITY: {state['data_quality_score']:.2f}\n\n"
                "Think step by step. Analyze each feature's weight.\n"
                "Produce a specific numerical prediction.\n"
                "End with CONFIDENCE: [0-1]"
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "model_runner")
            conf = extract_confidence(resp.content)
            return {"prediction": resp.content, "confidence": conf}

    def _validator(self, state: dict) -> dict:
        with self.monitor.track("validator"):
            ctx = (
                "Validate this prediction.\n"
                "PASS if well-reasoned (0.5+ with caveats).\n"
                "FAIL only for fundamental errors.\n"
                f"QUERY: {state['query']}\n"
                f"PREDICTION: {state['prediction'][:1500]}\n"
                "End with VALIDATION: PASS or VALIDATION: FAIL"
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "validator")
            passed = extract_validation(resp.content)
            return {
                "validation_result": resp.content,
                "validation_passed": passed,
                "validation_issues": [] if passed else [resp.content[:500]],
            }

    def _merge(self, state: dict) -> dict:
        with self.monitor.track("merge"):
            std_conf = state.get("confidence", 0.5)
            deb_conf = state.get("debate_confidence", 0.5)
            std_pred = state.get("prediction", "")[:1200]
            deb_pred = state.get("debate_consensus", "")[:1200]
            ctx = (
                "Merge two independent predictions. Weight by evidence quality.\n"
                f"STANDARD (confidence {std_conf:.2f}):\n{std_pred}\n\n"
                f"DEBATE (confidence {deb_conf:.2f}):\n{deb_pred}\n\n"
                "End with CONFIDENCE: [number]"
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "merge")
            conf = extract_confidence(resp.content)
            bonus = 0.1 if abs(std_conf - deb_conf) < 0.2 else -0.05
            final_conf = min(0.95, conf + bonus)
            return {"final_consensus": resp.content, "final_confidence": final_conf}

    def _social(self, state: dict) -> dict:
        with self.monitor.track("social_simulation"):
            result = self.social.run(
                query=state["query"],
                domain=state["domain"],
                agent_count=self.cfg.social_agents,
                rounds=self.cfg.social_rounds,
            )
            return {
                "social_report": result["social_report"],
                "confidence_modifier": result["confidence_modifier"],
                "sentiment_trajectory": result["sentiment_trajectory"],
                "social_total_actions": result["total_actions"],
            }

    def _statistical_baseline(self, state: dict) -> dict:
        """Optional statistical baseline forecast. Runs if [predict] extras installed.
        Produces side-by-side data that the merge node can optionally weight."""
        with self.monitor.track("statistical_baseline"):
            if self._baseline is None:
                return {"baseline": None, "baseline_method": "none"}
            try:
                result = self._baseline.forecast(
                    query=state["query"],
                    raw_data=state.get("raw_data", ""),
                    features=state.get("features", ""),
                )
                return {
                    "baseline": result,
                    "baseline_method": result.get("method", "none"),
                    "baseline_confidence": result.get("confidence"),
                }
            except Exception as e:
                return {
                    "baseline": None,
                    "baseline_method": "error",
                    "baseline_error": str(e),
                }

    def _reporter(self, state: dict) -> dict:
        with self.monitor.track("reporter"):
            final_conf = state.get("final_confidence", state.get("confidence", 0.5))
            if state.get("confidence_modifier") is not None:
                final_conf = max(
                    0.1, min(0.95, final_conf + state["confidence_modifier"] * 0.2)
                )

            # Build sections
            social_section = ""
            if state.get("run_social") and state.get("social_report"):
                social_section = (
                    f"\n=== SOCIAL SIMULATION ===\n"
                    f"Agents: {self.cfg.social_agents} | Rounds: {self.cfg.social_rounds}\n"
                    f"Sentiment: {state.get('sentiment_trajectory', [])}\n"
                    f"Modifier: {state.get('confidence_modifier', 0):+.2f}\n\n"
                    f"{state['social_report'][:1500]}\n"
                )

            ctx = (
                f"Generate executive report.\n"
                f"QUERY: {state['query']}\n"
                f"DOMAIN: {state['domain']} | MODE: {state['mode']}\n"
                f"DATA QUALITY: {state.get('data_quality_score', 0):.2f}\n\n"
                f"PREDICTION (confidence {final_conf:.2f}):\n"
                f"{state.get('final_consensus', state.get('prediction', 'No prediction'))[:2000]}\n\n"
                f"DISSENT: {state.get('dissent', 'None')[:500]}\n"
                f"{social_section}\n\n"
                "Format:\n"
                "EXECUTIVE_SUMMARY: [overview]\n"
                "FULL_PREDICTION: [expanded]\n"
                "RISK_ASSESSMENT: [risks]"
            )
            resp = self._cached_invoke([HumanMessage(content=ctx)], "reporter")
            content = resp.content

            parsed = extract_report_sections(content)
            return {
                "final_report": content,
                "executive_summary": parsed["executive_summary"] or content[:300],
                "risk_assessment": parsed["risk_assessment"]
                or "See prediction for risks",
                "final_confidence": parsed.get("confidence", final_conf),
                "status": "COMPLETED",
            }

    def _extract_confidence(self, text: str) -> float:
        """Extract confidence from LLM output using structured extraction first, then regex fallback."""
        return extract_confidence(text)

    def _extract_sections(self, text: str) -> tuple:
        """Extract Executive Summary and Risk Assessment from report."""
        parsed = extract_report_sections(text)
        return parsed["executive_summary"], parsed["risk_assessment"]
