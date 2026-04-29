"""Configuration integrator.

Applies a chosen SwarmProfile to the user's SwarmConfig and persists it.
Only this module touches the filesystem (config file).
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    yaml = None

from .registry import SwarmProfile
from .detector import HardwareProfile

CONFIG_DIR = Path.home() / ".config" / "smf-swarm"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def apply_profile(
    profile: SwarmProfile,
    hw: HardwareProfile | None = None,
    locked: bool = True,
) -> None:
    """Write profile + hardware snapshot into existing config file.

    Args:
        profile: The chosen SwarmProfile.
        hw: Optional hardware snapshot for audit trail.
        locked: If True, mark as locked so it survives re-runs.
    """
    existing = _load_raw() if CONFIG_FILE.exists() else {}

    existing["swarm"] = {
        "profile": profile.name,
        "profile_locked": locked,
        "agent_count": profile.agent_count,
        "social_agents": profile.agent_count,
        "max_steps": profile.max_steps,
        "social_rounds": max(1, profile.max_steps // 25),
        "llm_model": profile.llm_model,
        "llm_context_length": profile.llm_context_length,
    }

    if hw:
        existing["swarm"]["hardware_snapshot"] = {
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "total_ram_gb": round(hw.total_ram_gb, 2),
            "available_ram_gb": round(hw.available_ram_gb, 2),
            "vram_gb": round(hw.vram_gb, 2) if hw.vram_gb else None,
            "cpu_cores": hw.cpu_cores,
            "cpu_threads": hw.cpu_threads,
            "gpu_name": hw.gpu_name,
            "os_name": hw.os_name,
            "os_version": hw.os_version,
        }

    _save_raw(existing)


def get_current_profile() -> dict:
    """Return the current swarm profile block, or {} if not set."""
    raw = _load_raw()
    swarm = raw.get("swarm", {})
    if not swarm:
        return {}
    p_name = swarm.get("profile")
    if not p_name:
        return {}
    return {
        "name": p_name,
        "locked": swarm.get("profile_locked", False),
        "agent_count": swarm.get("agent_count"),
        "max_steps": swarm.get("max_steps"),
        "llm_model": swarm.get("llm_model"),
        "profile": swarm,
    }


def reset_profile() -> None:
    """Clear profile lock so next run will re-detect."""
    raw = _load_raw()
    if "swarm" in raw:
        raw["swarm"]["profile_locked"] = False
        _save_raw(raw)


def _load_raw() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    text = CONFIG_FILE.read_text()
    if yaml:
        return yaml.safe_load(text) or {}
    else:
        return json.loads(text)


def _save_raw(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if yaml:
        CONFIG_FILE.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False)
        )
    else:
        json_path = CONFIG_FILE.with_suffix(".json")
        json_path.write_text(json.dumps(data, indent=2))
