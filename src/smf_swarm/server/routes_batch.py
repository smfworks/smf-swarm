"""SMF Swarm Server — Batch Processing Router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from smf_swarm.server.models import BatchRequest, BatchResponse
from smf_swarm.server.runner import get_runner

router = APIRouter(prefix="/batch", tags=["batch"])


def get_auth():
    from smf_swarm.server.auth import AuthManager
    return AuthManager()


def get_ratelimiter():
    from smf_swarm.server.auth import RateLimiter
    return RateLimiter()


@router.post("", response_model=BatchResponse, status_code=202)
async def batch_predict(req: BatchRequest, auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    runner = get_runner()
    batch_id = runner.submit_batch([
        {
            "query": item.query,
            "mode": item.mode,
            "domain": item.domain,
            "context_text": item.context_text,
            "multi_sample": item.multi_sample,
        }
        for item in req.items
    ])
    return BatchResponse(
        batch_id=batch_id,
        status="queued",
        total=len(req.items),
        completed=0,
        failed=0,
        results=[],
    )


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: str):
    runner = get_runner()
    batch = runner.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Batch not found")

    failed = completed = 0
    results = []
    for job in batch.jobs:
        if job.status == "completed":
            completed += 1
            results.append(runner._result_to_dict(job.result) if job.result else {})
        elif job.status == "failed":
            failed += 1
            results.append({"error": job.error})
        else:
            results.append({"status": job.status, "progress": job.progress_pct})

    return BatchResponse(
        batch_id=batch_id,
        status=batch.status,
        total=len(batch.jobs),
        completed=completed,
        failed=failed,
        results=results,
        duration_s=batch.duration_s,
        completed_at=batch.completed_at,
    )
