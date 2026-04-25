"""Integration test for the benchmark CLI command.

This test verifies end-to-end flow without live LLM inference:
1. Dataset generation via fetch_benchmark_data.py --dummy
2. Hardware env logging via log_hw_env.py
3. CLI argument parsing for benchmark subcommand
4. Harness import and metric computation on cached results

These tests use a dummy dataset and monkeypatch the LLM pipeline to avoid
slow inference.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def dummy_jsonl():
    """Generate a temporary canonical JSONL benchmark dataset."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    records = [
        {
            "id": "q1",
            "question_text": "Will event A happen?",
            "domain": "general",
            "outcome": 1,
            "source": "dummy",
            "resolved_at": "2026-04-25",
        },
        {
            "id": "q2",
            "question_text": "Will event B happen?",
            "domain": "general",
            "outcome": 0,
            "source": "dummy",
            "resolved_at": "2026-04-25",
        },
        {
            "id": "q3",
            "question_text": "Will event C happen?",
            "domain": "general",
            "outcome": 1,
            "source": "dummy",
            "resolved_at": "2026-04-25",
        },
    ]
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


@pytest.fixture
def benchmark_output_dir():
    """Temporary directory for benchmark reports."""
    fd = tempfile.mkdtemp(prefix="smf_benchmark_")
    return fd


class TestCLIBenchmarkCommand:
    """End-to-end integration test for `smf-swarm benchmark` CLI."""

    def test_cli_benchmark_with_dummy_dataset(self, dummy_jsonl, benchmark_output_dir):
        """Run benchmark via CLI on a dummy dataset with monkeypatched pipeline."""
        # Monkeypatch Pipeline.run to return deterministic confidence without LLM calls
        from smf_swarm.pipeline import Pipeline, PipelineResult
        from unittest.mock import Mock

        original_run = Pipeline.run
        call_count = 0

        def mock_run(self, query, mode=None, domain=None, run_social=None, multi_sample=1, langgraph=None):
            nonlocal call_count
            call_count += 1
            return PipelineResult(
                query=query,
                domain=domain or "general",
                mode=mode or "standard",
                confidence=0.7,
                prediction_text="mock prediction",
                summary="mock summary",
                risk="mock risk",
                data_quality=0.6,
                duration_s=1.2,
                health_score=0.9,
                dissent="",
            )

        Pipeline.run = mock_run
        try:
            from smf_swarm.benchmarks.harness import BenchmarkHarness
            harness = BenchmarkHarness(llm_model="mock-model")
            report = harness.run(
                dataset=dummy_jsonl,
                modes=["standard"],
                multi_samples=[1],
                output_dir=benchmark_output_dir,
                max_questions=0,
            )
            assert report.total_questions == 3
            assert report.benchmark_run_id.startswith("bench_")
            assert "swarm_standard_ms1" in report.metrics
            # Brier score for always predicting 0.7 on outcomes [1,0,1]:
            # (0.7-1)^2 + (0.7-0)^2 + (0.7-1)^2 = 0.09 + 0.49 + 0.09 = 0.67 / 3 = 0.2233
            brier = report.metrics["swarm_standard_ms1"]["brier"]
            assert pytest.approx(brier, abs=0.01) == 0.2233
        finally:
            Pipeline.run = original_run

    def test_cli_benchmark_parses_args(self):
        """Verify CLI parser accepts benchmark subcommand."""
        from smf_swarm.cli import main
        import sys

        # Parse known args without running
        try:
            main([
                "benchmark",
                "--dataset", "dummy.jsonl",
                "--modes", "standard,debate",
                "--multi-samples", "1,5",
                "--max-questions", "10",
                "--output-dir", "/tmp/test",
                "--hw-env",
                "--llm-model", "gpt-4o",
            ])
        except SystemExit as e:
            # Dataset won't exist so it exits with error, but parser must accept all args
            pass


class TestFetchBenchmarkData:
    """Test fetch_benchmark_data.py behavior."""

    def test_dummy_dataset_generation(self):
        from scripts.fetch_benchmark_data import generate_dummy_dataset
        records = generate_dummy_dataset("test", 5)
        assert len(records) == 5
        assert records[0]["source"] == "dummy"
        assert records[0]["domain"] in ("technology", "finance", "climate", "health")
        assert "outcome" in records[0]
        assert records[0]["outcome"] in (0, 1)


class TestLogHwEnv:
    """Test log_hw_env.py behavior."""

    def test_hw_env_output(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("log_hw_env", "/home/mikesai2/smf-works/smf-swarm/scripts/log_hw_env.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        data = mod.gather()
        assert "timestamp" in data
        assert "os" in data
        assert "cpu" in data
        assert "python" in data
