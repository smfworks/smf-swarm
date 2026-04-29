"""SMF Swarm — Error monitoring, health tracking, and ETA estimation.

Tracks node execution times, errors, and health scores throughout the pipeline.
Maintains a lightweight historical database for per-node ETA estimation.
"""

from __future__ import annotations

import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

HISTORY_FILE = Path.home() / ".config" / "smf-swarm" / "node_history.json"


@dataclass
class NodeTiming:
    name: str
    start: float
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None


class SwarmMonitor:
    """Monitors pipeline health per node with ETA estimation."""

    def __init__(self):
        self.node_timings: list[NodeTiming] = []
        self.pipeline_start: Optional[float] = None
        self.pipeline_end: Optional[float] = None
        self.status: str = "idle"
        self._node_history: dict[str, float] = {}
        self._load_history()

    def _load_history(self):
        if HISTORY_FILE.exists():
            try:
                data = json.loads(HISTORY_FILE.read_text())
                # Average recent durations per node type
                for name, durations in data.items():
                    if durations:
                        self._node_history[name] = sum(durations) / len(durations)
            except (json.JSONDecodeError, OSError):
                pass

    def _save_history(self):
        existing: dict[str, list[float]] = {}
        if HISTORY_FILE.exists():
            try:
                existing = json.loads(HISTORY_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                existing = {}
        # Add new durations, keep last 20
        for nt in self.node_timings:
            if nt.duration and nt.success:
                existing.setdefault(nt.name, [])
                existing[nt.name].append(nt.duration)
                existing[nt.name] = existing[nt.name][-20:]
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            HISTORY_FILE.write_text(json.dumps(existing, indent=2))
        except OSError:
            pass

    def reset(self):
        """Clear all state for a fresh run."""
        self.node_timings = []
        self.pipeline_start = None
        self.pipeline_end = None
        self.status = "idle"

    def start_pipeline(self, query: str, mode: str):
        self.pipeline_start = time.time()
        self.status = "running"

    def end_pipeline(self, status: str = "completed"):
        self.pipeline_end = time.time()
        self.status = status
        duration = (
            (self.pipeline_end - self.pipeline_start) if self.pipeline_start else 0
        )
        errors = sum(1 for n in self.node_timings if not n.success)
        self._save_history()
        return {
            "pipeline_status": status,
            "pipeline_duration_s": round(duration, 2),
            "node_count": len(self.node_timings),
            "errors": errors,
            "health_score": round(
                max(0, 1.0 - errors / max(len(self.node_timings), 1)), 2
            ),
        }

    def estimate_remaining(self, total_expected_nodes: int) -> float:
        """Estimate remaining seconds based on historical data."""
        if not self.pipeline_start:
            return 0.0
        elapsed = time.time() - self.pipeline_start
        completed = len([n for n in self.node_timings if n.duration is not None])
        remaining_nodes = max(1, total_expected_nodes - completed)
        # Average historical duration for remaining node types (default 30s if unknown)
        avg_remaining = 0.0
        for name in self._node_history:
            if not any(
                n.name == name and n.duration is not None for n in self.node_timings
            ):
                avg_remaining += self._node_history.get(name, 30.0)
        if avg_remaining == 0:
            avg_remaining = remaining_nodes * 30.0
        # Blend elapsed with historical estimate
        return round(max(0, avg_remaining), 1)

    def start_node(self, name: str):
        self.node_timings.append(NodeTiming(name=name, start=time.time()))

    def end_node(self, name: str, success: bool = True, error: Optional[str] = None):
        for n in self.node_timings:
            if n.name == name and n.duration is None:
                n.duration = time.time() - n.start
                n.success = success
                n.error = error
                break

    def track(self, node_name: str):
        """Context manager for tracking a node."""
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            self.start_node(node_name)
            try:
                yield
                self.end_node(node_name, success=True)
            except Exception as e:
                self.end_node(node_name, success=False, error=str(e))
                raise

        return _ctx()
