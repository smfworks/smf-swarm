"""SMF Swarm Server — Enhanced Job Runner.

Wraps the existing in-memory JobRunner with batch support, listing, and cancel.
"""

from __future__ import annotations

import uuid
import time
import threading
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from smf_swarm.web.jobs import JobRunner, Job


@dataclass
class Batch:
    batch_id: str
    status: str = "queued"
    jobs: list[Job] = field(default_factory=list)
    total_jobs: int = 0
    completed_jobs: int = 0
    metrics: dict = field(default_factory=dict)
    duration_s: Optional[float] = None
    completed_at: Optional[str] = None


class ServerJobRunner:
    """Proxy that wraps JobRunner and adds batch / list / cancel support."""

    def __init__(self):
        self._inner = JobRunner()
        self._batches: dict[str, Batch] = {}
        self._batch_lock = threading.Lock()

    def submit(self, *args, **kwargs) -> str:
        return self._inner.submit(*args, **kwargs)

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._inner.get_job(job_id)

    def event_stream(self, job_id: str):
        return self._inner.event_stream(job_id)

    def _result_to_dict(self, result):
        return self._inner._result_to_dict(result)

    def submit_batch(self, items: list[dict]) -> str:
        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        jobs = []
        for item in items:
            job_id = self._inner.submit(
                query=item.get("query", ""),
                mode=item.get("mode", "debate"),
                domain=item.get("domain", "general"),
                context_text=item.get("context_text", ""),
                multi_sample=item.get("multi_sample", 1),
                langgraph=item.get("langgraph", True),
            )
            job = self._inner.get_job(job_id)
            jobs.append(job)

        with self._batch_lock:
            self._batches[batch_id] = Batch(
                batch_id=batch_id, status="running", jobs=jobs, total_jobs=len(jobs)
            )

        t = threading.Thread(target=self._monitor_batch, args=(batch_id,), daemon=True)
        t.start()
        return batch_id

    def _monitor_batch(self, batch_id: str):
        batch = self._batches.get(batch_id)
        if batch is None:
            return
        start = time.time()
        while True:
            done = sum(1 for j in batch.jobs if j.status in ("completed", "failed"))
            if done >= batch.total_jobs:
                batch.status = "completed"
                batch.completed_at = datetime.now().isoformat()
                batch.duration_s = round(time.time() - start, 2)
                confidences = [j.result.confidence for j in batch.jobs if j.result]
                if confidences:
                    batch.metrics = {
                        "mean_confidence": round(
                            sum(confidences) / len(confidences), 4
                        ),
                        "min_confidence": round(min(confidences), 4),
                        "max_confidence": round(max(confidences), 4),
                    }
                break
            time.sleep(0.2)

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        with self._batch_lock:
            return self._batches.get(batch_id)

    def submit_benchmark(
        self, dataset, modes, multi_samples, output_dir, llm_model
    ) -> str:
        batch_id = f"bench-{uuid.uuid4().hex[:12]}"
        batch = Batch(batch_id=batch_id, status="running", total_jobs=0)
        with self._batch_lock:
            self._batches[batch_id] = batch
        t = threading.Thread(
            target=self._run_benchmark,
            args=(batch_id, dataset, modes, multi_samples, output_dir, llm_model),
            daemon=True,
        )
        t.start()
        return batch_id

    def _run_benchmark(
        self, batch_id, dataset, modes, multi_samples, output_dir, llm_model
    ):
        batch = self._batches.get(batch_id)
        if batch is None:
            return
        start = time.time()
        try:
            from smf_swarm.benchmarks.harness import BenchmarkHarness

            harness = BenchmarkHarness()
            report = harness.run(
                dataset=dataset,
                modes=modes,
                multi_samples=multi_samples,
                output_dir=output_dir,
                llm_model=llm_model or None,
            )
            batch.status = "completed"
            batch.metrics = report.metrics if report else {}
        except Exception as exc:
            batch.status = "failed"
            batch.metrics = {"error": str(exc)}
        finally:
            batch.completed_at = datetime.now().isoformat()
            batch.duration_s = round(time.time() - start, 2)

    def list_jobs(self, limit: int = 50) -> list[Job]:
        with self._inner.lock:
            all_jobs = list(self._inner.jobs.values())
        all_jobs.sort(key=lambda j: j.created_at, reverse=True)
        return all_jobs[:limit]

    def cancel(self, job_id: str) -> bool:
        job = self._inner.get_job(job_id)
        if job is None or job.status in ("completed", "failed"):
            return False
        job.status = "failed"
        job.error = "Cancelled by user"
        job.completed_at = datetime.now().isoformat()
        return True


_server_runner: ServerJobRunner | None = None


def get_runner() -> ServerJobRunner:
    global _server_runner
    if _server_runner is None:
        _server_runner = ServerJobRunner()
    return _server_runner
