"""Cross-platform path helpers for SMF Swarm.

Centralizes cache, config, and data directory resolution so every submodule
uses the same XDG / Windows conventions consistently.

Windows:  %LOCALAPPDATA%\\SMF-Swarm\\Cache, %APPDATA%\\SMF-Swarm, ...
macOS:    ~/Library/Caches/smf-swarm, ~/Library/Application Support/smf-swarm
Linux:    ~/.cache/smf-swarm, ~/.config/smf-swarm (XDG)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _windows_cache() -> Path | None:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "SMF-Swarm" / "Cache"
    return None


def _windows_config() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "SMF-Swarm"
    return None


def _xdg_cache() -> Path:
    cache = os.environ.get("XDG_CACHE_HOME")
    if cache:
        return Path(cache) / "smf-swarm"
    return Path.home() / ".cache" / "smf-swarm"


def _xdg_config() -> Path:
    cfg = os.environ.get("XDG_CONFIG_HOME")
    if cfg:
        return Path(cfg) / "smf-swarm"
    return Path.home() / ".config" / "smf-swarm"


def default_cache_dir() -> Path:
    """Platform-appropriate cache directory."""
    if sys.platform == "win32":
        p = _windows_cache()
        if p:
            return p
    return _xdg_cache()


def default_config_dir() -> Path:
    """Platform-appropriate config directory."""
    if sys.platform == "win32":
        p = _windows_config()
        if p:
            return p
    return _xdg_config()


def default_data_dir() -> Path:
    """Platform-appropriate data directory (backtest DB, etc.)."""
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "SMF-Swarm" / "Data"
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "smf-swarm"
    return Path.home() / ".local" / "share" / "smf-swarm"
