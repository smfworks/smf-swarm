"""SMF Swarm Server — FastAPI Application Factory.

Usage:
    from smf_swarm.server import create_app
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("smf_swarm.server")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("SMF Swarm API server starting — v1.7.0")
    yield
    logger.info("SMF Swarm API server shutting down")


def create_app(
    token: str | None = None,
    rate_limit: tuple[int, int] | None = None,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    from smf_swarm.server.auth import AuthManager, RateLimiter
    from smf_swarm.server.routes_system import router as system_router
    from smf_swarm.server.routes_predict import router as predict_router
    from smf_swarm.server.routes_batch import router as batch_router
    from smf_swarm.server.routes_jobs import router as jobs_router
    from smf_swarm.server.routes_benchmark import router as benchmark_router
    from smf_swarm.server.routes_calibrate import router as calibrate_router

    _manager = AuthManager(token=token)
    _limiter = RateLimiter(
        max_requests=rate_limit[0] if rate_limit else 30,
        window_seconds=rate_limit[1] if rate_limit else 60,
    )

    def _auth():
        return _manager

    def _rl():
        return _limiter

    app = FastAPI(
        title="SMF Swarm API",
        description="Headless prediction, benchmark, and calibration API for SMF Swarm",
        version="1.7.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["*"],
    )

    @app.exception_handler(Exception)
    async def catch_all(request: Request, exc: Exception):
        logger.error("Uncaught exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "error_code": "internal_error"},
        )

    import smf_swarm.server.routes_predict as _rp
    import smf_swarm.server.routes_batch as _rb
    import smf_swarm.server.routes_jobs as _rj
    import smf_swarm.server.routes_benchmark as _rbm
    import smf_swarm.server.routes_calibrate as _rc

    app.dependency_overrides[_rp.get_auth] = _auth
    app.dependency_overrides[_rp.get_ratelimiter] = _rl
    app.dependency_overrides[_rb.get_auth] = _auth
    app.dependency_overrides[_rb.get_ratelimiter] = _rl
    app.dependency_overrides[_rj.get_auth] = _auth
    app.dependency_overrides[_rj.get_ratelimiter] = _rl
    app.dependency_overrides[_rbm.get_auth] = _auth
    app.dependency_overrides[_rbm.get_ratelimiter] = _rl
    app.dependency_overrides[_rc.get_auth] = _auth
    app.dependency_overrides[_rc.get_ratelimiter] = _rl

    app.include_router(system_router, prefix="/api/v1")
    app.include_router(predict_router, prefix="/api/v1")
    app.include_router(batch_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(benchmark_router, prefix="/api/v1")
    app.include_router(calibrate_router, prefix="/api/v1")

    return app
