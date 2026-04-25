"""SMF Swarm — Benchmarks package.

Public API:
    BenchmarkHarness.run(dataset_path, modes, output_dir)
    BenchmarkReport — dataclass for results
"""
from __future__ import annotations

from smf_swarm.benchmarks.harness import BenchmarkHarness, BenchmarkReport

__all__ = ["BenchmarkHarness", "BenchmarkReport"]
