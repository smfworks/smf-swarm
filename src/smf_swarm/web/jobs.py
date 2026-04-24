"""SMF Swarm — Web Job Queue.

In-memory async job runner with SSE-compatible event stream.
Each job runs in its own thread and yields progress events.
"""

from __future__ import annotations

import uuid
import threading
import queue
import time
from dataclasses import dataclass, field
from typing import Optional, Generator
from datetime import datetime

from smf_swarm.pipeline import Pipeline, PipelineResult
from smf_swarm.config import get_config


@dataclass
class JobEvent:
    """A single event emitted during pipeline execution."""
    type: str  # progress | result | error | log
    node: Optional[str] = None
    status: Optional[str] = None
    duration: Optional[float] = None
    message: Optional[str] = None
    result: Optional[dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = {"type": self.type, "timestamp": self.timestamp}
        if self.node is not None:
            d["node"] = self.node
        if self.status is not None:
            d["status"] = self.status
        if self.duration is not None:
            d["duration"] = self.duration
        if self.message is not None:
            d["message"] = self.message
        if self.result is not None:
            d["result"] = self.result
        return d


@dataclass
class Job:
    """A prediction job in the queue."""
    job_id: str
    query: str
    mode: str
    domain: str
    context_text: str = ""
    multi_sample: int = 1
    status: str = "queued"  # queued | running | completed | failed
    progress_pct: int = 0
    current_node: Optional[str] = None
    result: Optional[PipelineResult] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    events: queue.Queue = field(default_factory=queue.Queue)
    thread: Optional[threading.Thread] = None


class JobRunner:
    """Manages async prediction jobs."""

    NODE_ORDER = [
        "data_gatherer",
        "feature_engineer",
        "reflection",
        "model_runner",
        "validator",
        "debate",
        "merge",
        "social_simulation",
        "reporter",
    ]

    MODE_NODES = {
        "standard": ["data_gatherer", "feature_engineer", "reflection", "model_runner", "validator", "reporter"],
        "debate": ["data_gatherer", "feature_engineer", "debate", "reporter"],
        "full": ["data_gatherer", "feature_engineer", "reflection", "model_runner", "validator",
                 "debate", "merge", "social_simulation", "reporter"],
    }

    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def submit(
        self,
        query: str,
        mode: str = "debate",
        domain: str = "general",
        context_text: str = "",
        multi_sample: int = 1,
    ) -> str:
        """Queue a new prediction job. Returns job_id."""
        job_id = f"smf-{uuid.uuid4().hex[:12]}"
        job = Job(
            job_id=job_id,
            query=query,
            mode=mode,
            domain=domain,
            context_text=context_text,
        )
        with self.lock:
            self.jobs[job_id] = job

        job.thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        job.thread.start()
        return job_id

    def _run_job(self, job: Job):
        """Execute pipeline and emit events."""
        def emit(ev: JobEvent):
            job.events.put(ev)

        job.status = "running"
        emit(JobEvent(type="log", message=f"Job {job.job_id} started — mode: {job.mode}, domain: {job.domain}"))

        try:
            cfg = get_config()
            pipeline = Pipeline()
            
            # Prepend context_text to query if provided
            effective_query = job.query
            if job.context_text:
                effective_query = f"CONTEXT:\n{job.context_text[:4000]}\n\nQUERY: {job.query}"
                emit(JobEvent(type="log", message=f"Ingested context: {len(job.context_text)} chars"))

            emit(JobEvent(type="log", message="Spawning agents..."))

            # Track which nodes run for this mode
            expected_nodes = self.MODE_NODES.get(job.mode, self.MODE_NODES["debate"])
            total_nodes = len(expected_nodes)

            # Monkey-patch pipeline methods to capture progress
            originals = {}
            for node_name in expected_nodes:
                if hasattr(pipeline, f"_{node_name}"):
                    originals[node_name] = getattr(pipeline, f"_{node_name}")
                    setattr(pipeline, f"_{node_name}", self._wrap_node(pipeline, node_name, job, emit, total_nodes))

            result = pipeline.run(
                query=effective_query,
                mode=job.mode,
                domain=job.domain,
                run_social=(job.mode == "full"),
                multi_sample=job.multi_sample,
            )

            # Restore originals
            for node_name, orig in originals.items():
                setattr(pipeline, f"_{node_name}", orig)

            job.status = "completed"
            job.result = result
            job.completed_at = datetime.now().isoformat()
            job.progress_pct = 100

            emit(JobEvent(type="progress", node="reporter", status="complete", duration=result.duration_s))
            emit(JobEvent(type="result", result=self._result_to_dict(result)))
            emit(JobEvent(type="log", message=f"Completed in {result.duration_s:.0f}s | Confidence: {result.confidence:.2f}"))

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.now().isoformat()
            emit(JobEvent(type="error", message=str(e)))
            emit(JobEvent(type="log", message=f"FAILED: {e}"))

    def _wrap_node(self, pipeline, node_name: str, job: Job, emit, total_nodes: int):
        """Wrap a pipeline node method to emit progress events."""
        original = getattr(pipeline, f"_{node_name}")
        expected_nodes = self.MODE_NODES.get(job.mode, self.MODE_NODES["debate"])
        node_index = expected_nodes.index(node_name) if node_name in expected_nodes else 0

        def wrapped(state: dict) -> dict:
            job.current_node = node_name
            emit(JobEvent(type="progress", node=node_name, status="running"))
            t0 = time.time()
            try:
                result = original(state)
                duration = time.time() - t0
                job.progress_pct = min(99, int((node_index + 1) / total_nodes * 100))
                emit(JobEvent(type="progress", node=node_name, status="complete", duration=round(duration, 1)))
                return result
            except Exception as e:
                emit(JobEvent(type="progress", node=node_name, status="failed"))
                raise

        return wrapped

    def _result_to_dict(self, result: PipelineResult) -> dict:
        """Serialize PipelineResult to plain dict for JSON."""
        out = {
            "query": result.query,
            "domain": result.domain,
            "mode": result.mode,
            "confidence": result.confidence,
            "summary": result.summary,
            "risk": result.risk,
            "data_quality": result.data_quality,
            "duration_s": result.duration_s,
            "dissent": result.dissent,
            "timestamp": result.timestamp,
            "status": result.status,
            "prediction_text": result.prediction_text,
            "social_modifier": result.social_modifier,
            "health_score": result.health_score,
        }
        # v1.2.0+ fields
        if result.metadata.get("sentiment_trajectory"):
            out["sentiment_trajectory"] = result.metadata["sentiment_trajectory"]
        if result.metadata.get("multi_sample"):
            out["multi_sample"] = result.metadata["multi_sample"]
        if result.metadata.get("baseline"):
            out["baseline"] = result.metadata["baseline"]
        return out

    def get_job(self, job_id: str) -> Optional[Job]:
        with self.lock:
            return self.jobs.get(job_id)

    def event_stream(self, job_id: str) -> Generator[str, None, None]:
        """Yield SSE-formatted events for a job. Blocks until completion."""
        job = self.get_job(job_id)
        if job is None:
            yield f"event: error\ndata: {self._sse_data({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        seen_count = 0
        while True:
            try:
                ev = job.events.get(timeout=0.5)
                data = ev.to_dict()
                yield f"event: {data['type']}\ndata: {self._sse_data(data)}\n\n"
                if data["type"] in ("result", "error"):
                    break
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield f"event: heartbeat\ndata: {self._sse_data({'type': 'heartbeat'})}\n\n"
                if job.status in ("completed", "failed"):
                    break

    def _sse_data(self, data: dict) -> str:
        import json
        return json.dumps(data)


# Global singleton
runner = JobRunner()
