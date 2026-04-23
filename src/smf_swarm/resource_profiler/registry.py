"""Swarm profile registry.

Immutable profile definitions + filtering logic.
No I/O — pure functions operating on data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .detector import HardwareProfile


@dataclass(frozen=True)
class SwarmProfile:
    """A named bundle of swarm operational parameters."""
    name: str
    display_name: str
    ram_target_gb: float
    ram_min_gb: float
    agent_count: int
    max_steps: int
    llm_model: str
    llm_context_length: int
    description: str
    use_case: str
    priority: int  # Higher = more capable

    def to_config_dict(self) -> dict:
        """Convert to the subset of keys stored in SwarmConfig."""
        return {
            "name": self.name,
            "agent_count": self.agent_count,
            "max_steps": self.max_steps,
            "llm_model": self.llm_model,
            "llm_context_length": self.llm_context_length,
        }


# ─── Profile Definitions ─────────────────────────

ESSENTIAL = SwarmProfile(
    name="essential",
    display_name="Essential",
    ram_target_gb=6.0,
    ram_min_gb=4.0,
    agent_count=3,
    max_steps=20,
    llm_model="qwen2.5:3b",
    llm_context_length=4096,
    description="Barebones — minimal agents, minimal steps",
    use_case="Quick checks, small devices",
    priority=1,
)

COMPACT = SwarmProfile(
    name="compact",
    display_name="Compact",
    ram_target_gb=8.0,
    ram_min_gb=6.0,
    agent_count=5,
    max_steps=50,
    llm_model="qwen2.5:7b",
    llm_context_length=8192,
    description="Compact — the 8 GB baseline",
    use_case="Default baseline on most laptops",
    priority=2,
)

BALANCED = SwarmProfile(
    name="balanced",
    display_name="Balanced",
    ram_target_gb=12.0,
    ram_min_gb=8.0,
    agent_count=8,
    max_steps=100,
    llm_model="qwen2.5:7b",
    llm_context_length=8192,
    description="Balanced — good compromise between speed and depth",
    use_case="Standard predictions",
    priority=3,
)

DEEP = SwarmProfile(
    name="deep",
    display_name="Deep Analysis",
    ram_target_gb=20.0,
    ram_min_gb=16.0,
    agent_count=12,
    max_steps=200,
    llm_model="qwen2.5:14b",
    llm_context_length=16384,
    description="Deep — serious analysis with larger models",
    use_case="Deep financial/political analysis",
    priority=4,
)

ENSEMBLE = SwarmProfile(
    name="ensemble",
    display_name="Large Ensemble",
    ram_target_gb=36.0,
    ram_min_gb=32.0,
    agent_count=20,
    max_steps=400,
    llm_model="qwen2.5:32b",
    llm_context_length=32768,
    description="Large ensemble — maximum predictive depth",
    use_case="Maximum depth, institutional analysis",
    priority=5,
)

CLOUD = SwarmProfile(
    name="cloud",
    display_name="Cloud-Scale",
    ram_target_gb=80.0,
    ram_min_gb=64.0,
    agent_count=40,
    max_steps=800,
    llm_model="qwen2.5:72b",
    llm_context_length=32768,
    description="Cloud-scale — for server-class deployments",
    use_case="Server deployments, batch processing",
    priority=6,
)

ALL_PROFILES: list[SwarmProfile] = [
    ESSENTIAL, COMPACT, BALANCED, DEEP, ENSEMBLE, CLOUD,
]

# Safety: never recommend a profile that uses more than this fraction of total RAM.
SAFETY_MARGIN = 0.75


def filter_available_profiles(
    hw: HardwareProfile,
    safety_margin: float = SAFETY_MARGIN,
) -> list[SwarmProfile]:
    """Return all profiles that fit within the hardware envelope."""
    max_safe = hw.total_ram_gb * safety_margin
    if hw.has_gpu:
        max_safe += hw.vram_gb * 0.5  # VRAM is high-bandwidth; count 50%
    return [p for p in ALL_PROFILES if p.ram_target_gb <= max_safe]


def recommend_profile(
    available: list[SwarmProfile],
    fallback: SwarmProfile = ESSENTIAL,
) -> SwarmProfile:
    """Select the highest-priority available profile as the default recommendation."""
    if not available:
        return fallback
    return max(available, key=lambda p: p.priority)


def get_profile_by_name(name: str) -> Optional[SwarmProfile]:
    """Look up a profile by its programmatic name."""
    for p in ALL_PROFILES:
        if p.name == name:
            return p
    return None


def estimate_duration(profile: SwarmProfile) -> str:
    """Estimate wall-clock time for a profile run."""
    # Heuristic: each agent-step ≈ 2-5 seconds depending on model size
    per_step_s = {1: 2, 2: 2.5, 3: 3, 4: 4, 5: 5, 6: 5.5}.get(profile.priority, 3)
    total_s = profile.agent_count * profile.max_steps * per_step_s
    if total_s < 60:
        return f"~{int(total_s)}s"
    elif total_s < 3600:
        return f"~{round(total_s / 60, 0)} min"
    else:
        return f"~{round(total_s / 3600, 1)} hr"
