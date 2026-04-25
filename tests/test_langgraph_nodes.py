"""Unit tests for LangGraph node wrappers.

Every node is exercised with a mocked Pipeline to ensure wrappers:
  • Return the expected key/value shape.
  • Respect state["ok"] (skip on failure).
  • Populate state["node_timings"].
"""

from __future__ import annotations

import pytest
import sys
import time
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Ensure smf_swarm is importable from repo root
_repo = Path(__file__).resolve().parent.parent
_src = _repo / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from smf_swarm.pipeline_langgraph import (
    SwarmState,
    _make_node,
    _timing_tracker,
    LANGGRAPH_AVAILABLE,
)


@pytest.fixture
def pipeline():
    """Pipeline with all node methods mocked."""
    p = MagicMock()
    # Each node method returns a dict with its own name as a sentinel
    p._data_gatherer = MagicMock(return_value={"raw_data": "GATHERED"})
    p._feature_engineer = MagicMock(return_value={"features": "ENGINEERED"})
    p._statistical_baseline = MagicMock(
        return_value={"baseline": None, "baseline_method": "none"}
    )
    p._reflection = MagicMock(return_value={"reflection": "REFLECTED"})
    p._model_runner = MagicMock(return_value={"prediction": "RUN", "confidence": 0.75})
    p._validator = MagicMock(
        return_value={"validation_passed": True, "validation_result": "PASS"}
    )
    p._debate = None
    p._merge = MagicMock(return_value={"final_consensus": "MERGED", "final_confidence": 0.72})
    p._social = MagicMock(
        return_value={
            "social_report": "SOCIAL",
            "confidence_modifier": 0.05,
            "sentiment_trajectory": [0.1, 0.2],
        }
    )
    p._reporter = MagicMock(
        return_value={
            "final_report": "REPORT",
            "executive_summary": "SUMMARY",
            "risk_assessment": "RISKY",
            "final_confidence": 0.77,
            "status": "COMPLETED",
        }
    )
    p.debate = MagicMock()
    p.debate.run = MagicMock(
        return_value={"debate_consensus": "DEBATE", "debate_confidence": 0.70}
    )
    return p


@pytest.fixture
def ok_state() -> SwarmState:
    return {
        "query": "test",
        "domain": "general",
        "mode": "standard",
        "ok": True,
        "node_timings": {},
    }


# ── _timing_tracker ────────────────────────────────────────────


def test_timing_tracker_happy(pipeline, ok_state):
    result = _timing_tracker(pipeline, ok_state, "data_gatherer")
    assert result["raw_data"] == "GATHERED"
    assert "data_gatherer" in ok_state["node_timings"]
    assert ok_state["node_timings"]["data_gatherer"] >= 0.0


def test_timing_tracker_unknown_node(pipeline, ok_state):
    real_obj = object.__new__(type(pipeline))  # a plain object with no attrs
    result = _timing_tracker(real_obj, ok_state, "nonexistent")
    assert "error" in result
    # timing is NOT recorded for unknown nodes (early return)
    assert "nonexistent" not in ok_state.get("node_timings", {})


def test_timing_tracker_exception(pipeline, ok_state):
    pipeline._data_gatherer.side_effect = RuntimeError("boom")
    result = _timing_tracker(pipeline, ok_state, "data_gatherer")
    assert ok_state["ok"] is False
    assert "boom" in ok_state.get("error", "")


# ── Individual node wrappers ─────────────────────────────────


def test_data_gatherer(pipeline, ok_state):
    node = _make_node(pipeline, "data_gatherer")
    out = node(ok_state)
    assert out["raw_data"] == "GATHERED"
    assert "data_gatherer" in ok_state["node_timings"]


def test_feature_engineer(pipeline, ok_state):
    node = _make_node(pipeline, "feature_engineer")
    out = node(ok_state)
    assert out["features"] == "ENGINEERED"


def test_statistical_baseline(pipeline, ok_state):
    node = _make_node(pipeline, "statistical_baseline")
    out = node(ok_state)
    assert out["baseline_method"] == "none"


def test_reflection(pipeline, ok_state):
    node = _make_node(pipeline, "reflection")
    out = node(ok_state)
    assert out["reflection"] == "REFLECTED"


def test_model_runner(pipeline, ok_state):
    node = _make_node(pipeline, "model_runner")
    out = node(ok_state)
    assert out["confidence"] == 0.75


def test_validator(pipeline, ok_state):
    node = _make_node(pipeline, "validator")
    out = node(ok_state)
    assert out["validation_passed"] is True


def test_retry_model(pipeline, ok_state):
    """retry_model delegates to model_runner — verify it calls the same method."""
    node = _make_node(pipeline, "retry_model", "model_runner")
    out = node(ok_state)
    assert out["confidence"] == 0.75
    pipeline._model_runner.assert_called()


def test_debate(pipeline, ok_state):
    node = _make_node(pipeline, "debate")
    out = node(ok_state)
    assert out["debate_consensus"] == "DEBATE"
    pipeline.debate.run.assert_called_once()


def test_merge(pipeline, ok_state):
    node = _make_node(pipeline, "merge")
    out = node(ok_state)
    assert out["final_confidence"] == 0.72


def test_social(pipeline, ok_state):
    node = _make_node(pipeline, "social")
    out = node(ok_state)
    assert out["confidence_modifier"] == 0.05
    assert out["sentiment_trajectory"] == [0.1, 0.2]


def test_reporter(pipeline, ok_state):
    node = _make_node(pipeline, "reporter")
    out = node(ok_state)
    assert out["status"] == "COMPLETED"
    assert out["executive_summary"] == "SUMMARY"


# ── ok=False short-circuit ──────────────────────────────────


def test_node_skips_when_not_ok(pipeline, ok_state):
    ok_state["ok"] = False
    for name in (
        "data_gatherer",
        "feature_engineer",
        "reflection",
        "model_runner",
        "validator",
        "merge",
        "social",
        "reporter",
    ):
        node = _make_node(pipeline, name)
        out = node(ok_state)
        assert out == {}


# ── Node naming for LangGraph / tracing ──────────────────────


def test_node_has_proper_name(pipeline):
    node = _make_node(pipeline, "model_runner")
    assert node.__name__ == "model_runner"
