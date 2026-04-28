"""SMF Swarm Server — Benchmark Router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from smf_swarm.server.models import BenchmarkRequest, BenchmarkResponse
from smf_swarm.server.runner import get_runner

router = APIRouter(prefix="/benchmark", tags=["benchmarks"])


def get_auth():
    from smf_swarm.server.auth import AuthManager
    return AuthManager()


def get_ratelimiter():
    from smf_swarm.server.auth import RateLimiter
    return RateLimiter()


@router.post("", response_model=BenchmarkResponse, status_code=202)
async def benchmark(req: BenchmarkRequest, auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    runner = get_runner()
    batch_id = runner.submit_benchmark(
        dataset=req.dataset,
        modes=req.modes,
        multi_samples=req.multi_samples,
        output_dir=req.output_dir,
        llm_model=req.llm_model,
    )
    return BenchmarkResponse(
        batch_id=batch_id,
        status="queued",
        total=0,
        completed=0,
    )


@router.get("/{batch_id}", response_model=BenchmarkResponse)
async def get_benchmark(batch_id: str):
    runner = get_runner()
    batch = runner.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Benchmark not found")
    return BenchmarkResponse(
        batch_id=batch_id,
        status=batch.status,
        total=batch.total_jobs,
        completed=batch.completed_jobs,
        metrics=batch.metrics,
    )
