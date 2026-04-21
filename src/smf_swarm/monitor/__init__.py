"""SMF Swarm — Error monitoring and health tracking.

Tracks node execution times, errors, and health scores throughout the pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class NodeTiming:
    name: str
    start: float
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None


class SwarmMonitor:
    """Monitors pipeline health per node."""

    def __init__(self):
        self.node_timings: list[NodeTiming] = []
        self.pipeline_start: Optional[float] = None
        self.pipeline_end: Optional[float] = None
        self.status: str = "idle"

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
        duration = (self.pipeline_end - self.pipeline_start) if self.pipeline_start else 0
        errors = sum(1 for n in self.node_timings if not n.success)
        return {
            "pipeline_status": status,
            "pipeline_duration_s": round(duration, 2),
            "node_count": len(self.node_timings),
            "errors": errors,
            "health_score": round(max(0, 1.0 - errors / max(len(self.node_timings), 1)), 2),
        }

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
