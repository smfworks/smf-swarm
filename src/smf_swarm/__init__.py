"""SMF Swarm — LangGraph + CrewAI + Social Swarm Hybrid Predictive Pipeline.

Predict the future with agent swarms. Run three modes — Standard, Debate, and
Full+Social — seeded with any LLM provider you choose (local or cloud).

Example:
    from smf_swarm import Pipeline
    result = Pipeline("Will NVIDIA market cap exceed $4T by 2026?", mode="full", domain="financial")
    print(result.final_confidence, result.executive_summary)
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "SMF Works"
__contact__ = "michael@smfworks.com"
__license__ = "MIT"

from smf_swarm.pipeline import Pipeline, PipelineResult
from smf_swarm.config import configure, get_config, load_config

__all__ = [
    "Pipeline",
    "PipelineResult",
    "configure",
    "get_config",
    "load_config",
    "__version__",
]
