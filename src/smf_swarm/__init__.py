"""SMF Swarm — Custom Sequential Hybrid Pipeline with Adversarial Debate and Social Calibration.

Predict the future with agent swarms. Run three modes — Standard, Debate, and
Full+Social — powered by any LLM provider you choose (local or cloud).

Example:
    from smf_swarm import Pipeline
    result = Pipeline("Will NVIDIA market cap exceed $4T by 2026?", mode="full", domain="financial")
    print(result.confidence, result.summary)
"""

from __future__ import annotations

__version__ = "1.5.0"
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
