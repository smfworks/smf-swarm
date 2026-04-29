"""SMF Swarm — Resource Profiler Package.

Hardware-aware adaptive scaling with user override.

Usage:
    from smf_swarm.resource_profiler import detect_hardware, recommend_profile, prompt_profile

    hw = detect_hardware()
    rec = recommend_profile(hw)
    chosen = prompt_profile(hw, recommended=rec)  # blocks for user input
    apply_profile(chosen)  # persists to config
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path

from .detector import detect_hardware, HardwareProfile
from .registry import (
    SwarmProfile,
    ALL_PROFILES,
    filter_available_profiles,
    recommend_profile,
)
from .prompter import prompt_profile, format_profile_table
from .configurator import apply_profile, get_current_profile, reset_profile

__all__ = [
    "detect_hardware",
    "HardwareProfile",
    "SwarmProfile",
    "ALL_PROFILES",
    "filter_available_profiles",
    "recommend_profile",
    "prompt_profile",
    "format_profile_table",
    "apply_profile",
    "get_current_profile",
    "reset_profile",
]


# ── Convenience API ──────────────────────────────


def run_profiler(
    auto: bool = False,
    force: bool = False,
    input_func: Callable[[str], str] | None = None,
) -> SwarmProfile:
    """Full profiler lifecycle: detect → recommend → (prompt/apply) → return.

    Args:
        auto:      Skip user prompt; auto-apply the recommended profile.
        force:     Ignore previously-locked profile; re-profile.
        input_func: Override `input()` for testing.

    Returns:
        The chosen SwarmProfile.
    """
    # Check for locked profile unless forced
    if not force:
        current = get_current_profile()
        if current and current["locked"]:
            return SwarmProfile(**current["profile"])

    hw = detect_hardware()
    available = filter_available_profiles(hw)
    recommended = recommend_profile(available)

    if auto:
        apply_profile(recommended, hw, locked=True)
        return recommended

    chosen = prompt_profile(hw, available, recommended, input_func=input_func)
    apply_profile(chosen, hw, locked=True)
    return chosen
