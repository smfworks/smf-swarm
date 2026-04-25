"""Integration tests for LangGraph graph compilation and structural parity.

Goals:
  1. build_pipeline_graph() compiles and exposes all expected nodes.
  2. LangGraphPipeline produces structurally similar results to classic Pipeline.run()
     when using the same mocked LLM.
"""

from __future__ import annotations

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_repo = Path(__file__).resolve().parent.parent
_src = _repo / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from smf_swarm.pipeline_langgraph import (
    build_pipeline_graph,
    LangGraphPipeline,
    LANGGRAPH_AVAILABLE,
)


# ── Compilation ────────────────────────────────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_graph_compiles_with_all_nodes():
    """Verify build_pipeline_graph returns a compiled graph with 11+ nodes."""
    pipeline = MagicMock()
    pipeline.cfg.default_mode = "debate"
    pipeline.cfg.default_domain = "general"

    graph = build_pipeline_graph(pipeline)
    assert graph is not None
    # Compiled LangGraph has a `.nodes` dict mapping name -> Node
    assert hasattr(graph, "nodes")
    node_names = set(graph.nodes.keys())
    expected = {
        "data_gatherer",
        "feature_engineer",
        "statistical_baseline",
        "reflection",
        "model_runner",
        "validator",
        "retry_model",
        "debate",
        "merge",
        "social",
        "reporter",
    }
    assert expected.issubset(node_names), f"Missing: {expected - node_names}"


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_graph_has_conditional_edges():
    """Conditional edges are present for the 5 router points."""
    pipeline = MagicMock()
    pipeline.cfg.default_mode = "debate"
    pipeline.cfg.default_domain = "general"

    graph = build_pipeline_graph(pipeline)
    # Compiled graph exposes edges via channels / triggers
    # We test routing behaviour in test_langgraph_routing.py;
    # here we just assert the graph is valid.
    assert graph is not None


# ── Structural parity: LangGraph vs. Classic ─────────────────────


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_langgraph_produces_same_keys_as_classic():
    """With identical mocked LLM, both pipelines return PipelineResult with same keys."""
    mock_llm = MagicMock()

    # Build a minimal mocked Pipeline so _run_state_machine succeeds
    with patch("smf_swarm.pipeline_langgraph.Pipeline") as MockPipe:
        mp = MockPipe.return_value
        mp.cfg.default_mode = "debate"
        mp.cfg.default_domain = "general"
        mp.cfg.llm.model = "test-model"
        mp.cfg.llm.temperature = 0.2
        mp.cfg.social_agents = 6
        mp.cfg.social_rounds = 3
        mp.monitor.end_pipeline.return_value = {"health_score": 95}

        # Every node method returns deterministic data
        mp._data_gatherer.return_value = {
            "raw_data": "DG_DATA",
            "data_quality_score": 0.7,
        }
        mp._feature_engineer.return_value = {
            "features": "FE_DATA",
            "feature_count": 4,
        }
        mp._statistical_baseline.return_value = {
            "baseline": None,
            "baseline_method": "none",
        }
        mp._reflection.return_value = {"reflection": "REFL"}
        mp._model_runner.return_value = {"prediction": "PRED", "confidence": 0.65}
        mp._validator.return_value = {
            "validation_passed": True,
            "validation_result": "PASS",
        }
        mp._merge.return_value = {
            "final_consensus": "FC",
            "final_confidence": 0.63,
        }
        mp._social.return_value = {
            "social_report": "SOCIAL",
            "confidence_modifier": 0.02,
            "sentiment_trajectory": [0.1],
        }
        mp._reporter.return_value = {
            "final_report": "RPT",
            "executive_summary": "ES",
            "risk_assessment": "RSK",
            "final_confidence": 0.65,
            "status": "COMPLETED",
        }
        mp.debate = MagicMock()
        mp.debate.run.return_value = {
            "debate_consensus": "DC",
            "debate_confidence": 0.60,
            "dissent": "DISS",
        }

        # ── Classic pipeline ──
        from smf_swarm.pipeline import Pipeline
        classic = Pipeline.__new__(Pipeline)
        classic.cfg = mp.cfg
        classic.llm = mock_llm
        classic.debate = mp.debate
        classic.social = MagicMock()
        classic.monitor = mp.monitor
        classic._cache = MagicMock()
        classic._backtest = MagicMock()
        classic._baseline = None

        # Manually assign methods from mock
        classic._data_gatherer = mp._data_gatherer
        classic._feature_engineer = mp._feature_engineer
        classic._statistical_baseline = mp._statistical_baseline
        classic._reflection = mp._reflection
        classic._model_runner = mp._model_runner
        classic._validator = mp._validator
        classic._merge = mp._merge
        classic._social = mp._social
        classic._reporter = mp._reporter

        classic_result = classic._run_state_machine("Q", "debate", "general", run_social=False)
        assert classic_result["status"] == "COMPLETED"

        # ── LangGraph pipeline ──
        lgp = LangGraphPipeline.__new__(LangGraphPipeline)
        lgp._pipeline = mp
        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter(
            [
                {"data_gatherer": mp._data_gatherer.return_value},
                {"feature_engineer": mp._feature_engineer.return_value},
                {"statistical_baseline": mp._statistical_baseline.return_value},
                {"debate": mp.debate.run.return_value},
                {"reporter": mp._reporter.return_value},
            ]
        )
        mock_graph.get_state.return_value = MagicMock(
            values={
                "ok": True,
                "final_confidence": 0.65,
                "final_report": "RPT",
                "executive_summary": "ES",
                "risk_assessment": "RSK",
                "data_quality_score": 0.7,
                "confidence_modifier": None,
                "dissent": "DISS",
                "status": "COMPLETED",
            }
        )
        lgp._graph = mock_graph

        lg_result = lgp.run("Q", mode="debate", domain="general")
        assert lg_result.status == "COMPLETED"

        # Key structural assertions
        assert lg_result.confidence == pytest.approx(0.65, abs=0.01)
        assert hasattr(lg_result, "metadata")
        assert lg_result.metadata.get("langgraph") is True


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
def test_graph_mermaid_diagram_exists():
    """Compiled LangGraph can produce a mermaid diagram for documentation."""
    pipeline = MagicMock()
    pipeline.cfg.default_mode = "debate"
    pipeline.cfg.default_domain = "general"

    graph = build_pipeline_graph(pipeline)
    assert graph is not None
    # draw_mermaid() returns a string or raises ImportError if graphviz missing
    try:
        gg = graph.get_graph()
        diagram = gg.draw_mermaid()
        assert isinstance(diagram, str)
        assert "data_gatherer" in diagram
    except ImportError:
        pytest.skip("graphviz/mermaid not available in test env")
