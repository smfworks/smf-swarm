"""SMF Swarm Server — Job Status & Management Router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from smf_swarm.server.models import JobStatusResponse
from smf_swarm.server.runner import get_runner

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_auth():
    from smf_swarm.server.auth import AuthManager
    return AuthManager()


def get_ratelimiter():
    from smf_swarm.server.auth import RateLimiter
    return RateLimiter()


@router.get("/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str, auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    runner = get_runner()
    job = runner.get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    result = runner._result_to_dict(job.result) if job.result else None
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress_pct=job.progress_pct,
        current_node=job.current_node,
        query=job.query,
        mode=job.mode,
        domain=job.domain,
        created_at=job.created_at,
        completed_at=job.completed_at,
        duration_s=job.duration_s,
        result=result,
        error=job.error,
    )


@router.get("")
async def list_jobs(auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    runner = get_runner()
    jobs = runner.list_jobs(limit=50)
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j.job_id,
                "status": j.status,
                "query": j.query,
                "mode": j.mode,
                "progress_pct": j.progress_pct,
                "current_node": j.current_node,
                "created_at": j.created_at,
                "completed_at": j.completed_at,
            }
            for j in jobs
        ],
    }


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(job_id: str, auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    runner = get_runner()
    ok = runner.cancel(job_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found or already completed")
    return None
