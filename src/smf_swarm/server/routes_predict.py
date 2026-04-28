"""SMF Swarm Server — Prediction Router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from smf_swarm.server.models import PredictRequest, PredictResponse
from smf_swarm.server.runner import get_runner
from smf_swarm.server.async_jobs import event_stream

router = APIRouter(prefix="/predict", tags=["predictions"])


def get_auth():
    from smf_swarm.server.auth import AuthManager
    return AuthManager()


def get_ratelimiter():
    from smf_swarm.server.auth import RateLimiter
    return RateLimiter()


@router.post("", response_model=PredictResponse, status_code=202)
async def predict(req: PredictRequest, auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    runner = get_runner()
    job_id = runner.submit(
        query=req.query,
        mode=req.mode,
        domain=req.domain,
        context_text=req.context_text,
        multi_sample=req.multi_sample,
        langgraph=req.langgraph,
    )
    return PredictResponse(
        job_id=job_id,
        status="queued",
        started_at=runner.get_job(job_id).created_at,
    )


@router.get("/stream/{job_id}")
async def stream(job_id: str):
    return event_stream(job_id)
