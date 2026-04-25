# Minimal smoke tests for smf_swarm

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

def test_import():
    import smf_swarm
    assert smf_swarm.__version__ == "1.4.0"

def test_config_default():
    from smf_swarm.config import SwarmConfig
    cfg = SwarmConfig()
    assert cfg.default_mode == "standard"
    assert cfg.social_agents == 15

def test_pipeline_init():
    from smf_swarm.config import LLMConfig
    from smf_swarm.pipeline import Pipeline
    # We can't fully init without LLM, but we can test the dataclass
    cfg = LLMConfig()
    assert cfg.provider == "ollama"
