#!/usr/bin/env python3
"""End-to-end parity test: classic sequential pipeline vs LangGraph backend.

Run:
    cd /home/mikesai2/smf-works/smf-swarm
    .venv/bin/python tests/e2e_parity_test.py

Returns 0 if parity is within tolerance, 1 if critical mismatch, 2 on crash.
"""
import sys
import os
import re
from dataclasses import asdict
from unittest.mock import MagicMock

# Allow imports from src/ during local execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from smf_swarm.pipeline import Pipeline, PipelineResult

# ── Mock LLM backend ─────────────────────────────────────────

class FakeLLM:
    """Deterministic mock ChatOpenAI. Returns canned responses based on prompt keywords."""

    _call_count = 0

    def __init__(self, **kwargs):
        pass

    def invoke(self, messages, **kwargs):
        self._call_count += 1
        text = ""
        if messages:
            text = getattr(messages[0], "content", str(messages[0]))
        resp = self._pick_response(text)
        mock = MagicMock()
        mock.content = resp
        return mock

    def _pick_response(self, text: str) -> str:
        lower = text.lower()
        if "data sources" in lower or "data_gatherer" in lower or "gather data" in lower:
            return (
                "Key sources: industry reports, peer-reviewed studies, news.\n"
                "Historical precedents: similar shifts took 18-24 months.\n"
                "Current indicators: adoption rate 42% and climbing.\n"
                "DATA_QUALITY_SCORE: 0.75"
            )
        if "engineer predictive features" in lower or "feature_engineer" in lower:
            return (
                "1. Adoption-rate trajectory\n"
                "2. Regulatory tailwinds\n"
                "3. Cost-reduction curve\n"
                "4. Competitor dynamics\n"
                "5. Talent availability\n"
                "FEATURE_COUNT: 5"
            )
        if "reflection" in lower or "base rate" in lower:
            return (
                "Base rate: 55% for tech-adoption curves over 24 months.\n"
                "Strongest evidence: regulatory filing indicates intent.\n"
                "Most likely wrong: macro shocks, regulatory reversal.\n"
                "Mind changing: three consecutive months >58%."
            )
        if "prediction" in lower and "confidence" in lower:
            return (
                "Step-by-step: adoption currently 42%, trajectory +2.3%/mo.\n"
                "By end of year should reach ~61%.\n"
                "CONFIDENCE: 0.68"
            )
        if "validate" in lower:
            return "VALIDATION: PASS"
        if "debate" in lower or "dissent" in lower:
            return (
                "DISSENT: Uncertainty in regulatory timeline could delay by 6+ months.\n"
                "CONFIDENCE: 0.62"
            )
        if "merge" in lower or "merge two independent" in lower:
            return (
                "Merged: weighted average of standard (0.68) and debate (0.62).\n"
                "Consensus leans slightly toward standard due to stronger data.\n"
                "CONFIDENCE: 0.65"
            )
        if "social" in lower or "simulation" in lower:
            return (
                "Social simulation complete.\n"
                "Agents trending bullish after 3 rounds.\n"
                "Modifier: +0.08"
            )
        # default / reporter
        return (
            "EXECUTIVE_SUMMARY: Adoption likely to exceed 60% by end 2026 (0.65 confidence).\n"
            "FULL_PREDICTION: Gradual ramp to 61-63% by Q4.\n"
            "RISK_ASSESSMENT: Regulatory reversal, macro shock."
        )


# ── Helpers ──────────────────────────────────────────────────

def result_to_dict(r: PipelineResult) -> dict:
    d = asdict(r)
    # Scrub volatile fields
    d.pop("timestamp", None)
    d["metadata"] = {k: v for k, v in d.get("metadata", {}).items()
                     if k not in ("node_timings", "start_time")}
    return d


def diff_results(a: PipelineResult, b: PipelineResult, tol: float = 0.05) -> list[str]:
    issues = []
    da, db = result_to_dict(a), result_to_dict(b)
    keys = set(da) | set(db)
    for k in sorted(keys):
        va, vb = da.get(k), db.get(k)
        if isinstance(va, float) and isinstance(vb, float):
            if abs(va - vb) > tol:
                issues.append(f"  {k}: classic={va:.3f}  langgraph={vb:.3f}  Δ>{tol}")
        elif va != vb:
            # For text fields, do a soft similarity check
            if isinstance(va, str) and isinstance(vb, str):
                # Check if executive summaries contain the core claim
                if k in ("summary", "prediction_text"):
                    a_core = bool(re.search(r"exceed 60%|61%|adoption", va, re.I))
                    b_core = bool(re.search(r"exceed 60%|61%|adoption", vb, re.I))
                    if a_core != b_core:
                        issues.append(f"  {k}: core claim mismatch")
                    continue
            issues.append(f"  {k}: classic={va!r}  langgraph={vb!r}")
    return issues


# ── Main ─────────────────────────────────────────────────────

def run_comparison(query: str, mode: str, domain: str) -> tuple[PipelineResult, PipelineResult]:
    """Run once in classic mode, once in LangGraph mode."""

    # Classic
    print(f"\n[CLASSIC]  mode={mode}  query='{query}'")
    classic_pipe = Pipeline(llm=FakeLLM())
    classic = classic_pipe.run(query=query, mode=mode, domain=domain, langgraph=False)
    print(f"  confidence={classic.confidence:.3f}  duration={classic.duration_s:.1f}s  status={classic.status}")

    # LangGraph
    print(f"[LANGGRAPH] mode={mode}  query='{query}'")
    lg_pipe = Pipeline(llm=FakeLLM())
    lg = lg_pipe.run(query=query, mode=mode, domain=domain, langgraph=True)
    print(f"  confidence={lg.confidence:.3f}  duration={lg.duration_s:.1f}s  status={lg.status}")

    # Inspect metadata flags
    lg_meta = lg.metadata or {}
    classic_meta = classic.metadata or {}
    print(f"  lg.backend={lg_meta.get('langgraph')}  cl.backend={classic_meta.get('langgraph')} (expected False)")

def main() -> int:
    os.environ.setdefault("LANGGRAPH_AUTO", "1")
    print("=" * 60)
    print("SMF Swarm v1.4.1 — End-to-End LangGraph Parity Test")
    print("=" * 60)

    query = "Will AI agent adoption exceed 60% by end of 2026?"
    domain = "technology"

    modes = ["standard", "debate", "full"]
    exit_code = 0
    for mode in modes:
        try:
            run_comparison(query, mode, domain)
        except Exception as exc:
            print(f"  [ERROR] mode={mode}: {exc}")
            import traceback
            traceback.print_exc()
            return 2

    print("\n" + "=" * 60)
    print("PARITY SUMMARY")
    print("=" * 60)

    # Final detailed comparison for full mode
    print("\n[DETAILED COMPARISON] mode=full")
    classic_full = Pipeline(llm=FakeLLM()).run(query=query, mode="full", domain=domain, langgraph=False)
    lg_full = Pipeline(llm=FakeLLM()).run(query=query, mode="full", domain=domain, langgraph=True)

    issues = diff_results(classic_full, lg_full, tol=0.10)
    if issues:
        print("  Mismatches (>0.10 tolerance):")
        for i in issues:
            print(i)
        exit_code = 1
    else:
        print("  All fields within tolerance. Parity OK.")

    print("\nDone.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
