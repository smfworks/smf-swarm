"""Unit tests for LangGraphPipeline and create_pipeline factory.

Covers:
  • Constructor behaviour (ImportError when langgraph absent).
  • run() with mocked graph.stream().
  • stream_callback invocation per node.
  • resume() from checkpoint.
  • create_pipeline() env-var / preference logic.
"""

from __future__ import annotations

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_repo = Path(__file__).resolve().parent.parent
_src = _repo / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import smf_swarm.pipeline_langgraph as lgp_mod
from smf_swarm.pipeline_langgraph import (
    LangGraphPipeline,
    create_pipeline,
    LANGGRAPH_AVAILABLE,
)

# ── Constructor ────────────────────────────────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_constructor_raises_when_langgraph_unavailable():
    with patch.object(lgp_mod, "LANGGRAPH_AVAILABLE", False):
        with patch.object(lgp_mod, "build_pipeline_graph", lambda _: None):
            with pytest.raises(ImportError):
                LangGraphPipeline()


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_constructor_compiles_graph():
    """Sanity: LangGraphPipeline can be instantiated with a mocked Pipeline."""
    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipeline:
        mp = MockPipeline.return_value
        mp.cfg.default_mode = "debate"
        mp.cfg.default_domain = "general"
        mp.cfg.social_agents = 6
        mp.cfg.social_rounds = 3
        mp.monitor.end_pipeline.return_value = {"health_score": 95}
        lgp = LangGraphPipeline(llm=MagicMock())
        assert lgp._graph is not None


# ── LangGraphPipeline.run() ───────────────────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_run_standard_mode():
    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipeline:
        mp = MockPipeline.return_value
        mp.cfg.default_mode = "standard"
        mp.cfg.default_domain = "general"
        mp.monitor.end_pipeline.return_value = {"health_score": 90}

        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter([])
        mock_graph.get_state.return_value = MagicMock(
            values={
                "ok": True,
                "final_confidence": 0.72,
                "final_report": "REPORT",
                "executive_summary": "SUM",
                "risk_assessment": "LOW",
                "data_quality_score": 0.8,
                "confidence_modifier": None,
                "dissent": "",
                "status": "COMPLETED",
            }
        )

        lgp = LangGraphPipeline.__new__(LangGraphPipeline)
        lgp._pipeline = mp
        lgp._graph = mock_graph

        result = lgp.run("Will X happen?", mode="standard", domain="technology")

        assert result.confidence == 0.72
        assert result.mode == "standard"
        assert result.domain == "technology"
        assert result.status == "COMPLETED"
        assert result.metadata.get("langgraph") is True


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_run_multi_sample_falls_back():
    """multi_sample>1 delegates to Pipeline.run() for identical semantics."""
    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipeline:
        mp = MockPipeline.return_value
        mp.cfg.default_mode = "debate"
        mp.cfg.default_domain = "general"

        lgp = LangGraphPipeline.__new__(LangGraphPipeline)
        lgp._pipeline = mp
        lgp._graph = MagicMock()

        lgp.run("test", multi_sample=3)
        mp.run.assert_called_once()
        call_kwargs = mp.run.call_args.kwargs
        assert call_kwargs["multi_sample"] == 3


# ── stream_callback ───────────────────────────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_stream_callback_invoked():
    calls = []

    def cb(node_name: str, update: dict):
        calls.append((node_name, list(update.keys())))

    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipeline:
        mp = MockPipeline.return_value
        mp.cfg.default_mode = "debate"
        mp.cfg.default_domain = "general"
        mp.monitor.end_pipeline.return_value = {"health_score": 100}

        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter(
            [
                {"data_gatherer": {"raw_data": "R"}},
                {"feature_engineer": {"features": "F"}},
                {"reporter": {"final_report": "DONE"}},
            ]
        )
        mock_graph.get_state.return_value = MagicMock(
            values={
                "ok": True,
                "final_confidence": 0.5,
                "final_report": "DONE",
                "executive_summary": "ES",
                "status": "COMPLETED",
            }
        )

        lgp = LangGraphPipeline.__new__(LangGraphPipeline)
        lgp._pipeline = mp
        lgp._graph = mock_graph

        lgp.run("stream test", stream_callback=cb)

        assert len(calls) >= 2
        assert calls[0][0] == "data_gatherer"
        assert calls[1][0] == "feature_engineer"


# ── resume() ────────────────────────────────────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_resume_from_checkpoint():
    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipeline:
        mp = MockPipeline.return_value
        mp.cfg.default_mode = "debate"
        mp.cfg.default_domain = "general"

        mock_graph = MagicMock()
        mock_graph.get_state.return_value = MagicMock(
            values={
                "query": "Q",
                "domain": "general",
                "mode": "debate",
                "final_confidence": 0.66,
                "final_report": "R",
                "executive_summary": "E",
                "status": "COMPLETED",
                "ok": True,
            },
            next=["reporter"],  # graph interrupted, not finished
        )
        mock_graph.stream.return_value = iter([])

        lgp = LangGraphPipeline.__new__(LangGraphPipeline)
        lgp._pipeline = mp
        lgp._graph = mock_graph

        result = lgp.resume(thread_id="tid-42")
        assert result is not None
        assert result.confidence == 0.66
        assert result.metadata.get("resumed") is True


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_resume_none_when_no_checkpoint():
    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipeline:
        mp = MockPipeline.return_value
        mp.cfg.default_mode = "debate"
        mp.cfg.default_domain = "general"

        mock_graph = MagicMock()
        mock_graph.get_state.return_value = None  # no checkpoint

        lgp = LangGraphPipeline.__new__(LangGraphPipeline)
        lgp._pipeline = mp
        lgp._graph = mock_graph

        assert lgp.resume("nonexistent") is None


# ── create_pipeline() factory ─────────────────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_create_pipeline_prefers_langgraph():
    with patch.object(lgp_mod, "LANGGRAPH_AVAILABLE", True):
        with patch.object(lgp_mod, "LangGraphPipeline") as MockLGP:
            MockLGP.return_value = "LGP_INSTANCE"
            p = create_pipeline()
            assert p == "LGP_INSTANCE"


def test_create_pipeline_fallback_classic():
    with patch.object(lgp_mod, "LANGGRAPH_AVAILABLE", False):
        with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipe:
            MockPipe.return_value = "CLASSIC"
            p = create_pipeline()
            assert p == "CLASSIC"


def test_create_pipeline_env_disable():
    with patch.object(lgp_mod, "LANGGRAPH_AVAILABLE", True):
        with patch.dict(os.environ, {"LANGGRAPH_DISABLE": "1"}):
            with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipe:
                MockPipe.return_value = "CLASSIC_ENV"
                p = create_pipeline()
                assert p == "CLASSIC_ENV"


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_create_pipeline_explicit_false():
    with patch.object(lgp_mod, "LANGGRAPH_AVAILABLE", True):
        with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipe:
            MockPipe.return_value = "CLASSIC_ARG"
            p = create_pipeline(prefer_langgraph=False)
            assert p == "CLASSIC_ARG"


def test_create_pipeline_explicit_true_raises():
    with patch.object(lgp_mod, "LANGGRAPH_AVAILABLE", False):
        with pytest.raises(ImportError):
            create_pipeline(prefer_langgraph=True)
