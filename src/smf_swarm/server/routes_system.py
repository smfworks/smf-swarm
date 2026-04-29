"""SMF Swarm Server — Config & Health Router."""

from __future__ import annotations

from fastapi import APIRouter
from smf_swarm.server.models import ConfigResponse, HealthResponse

router = APIRouter(prefix="", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health():
    pipeline_ok = True
    langgraph_ok = False
    try:
        from smf_swarm.pipeline import _LANGGRAPH_AVAILABLE

        langgraph_ok = _LANGGRAPH_AVAILABLE
    except Exception:
        pass
    return HealthResponse(
        status="ok",
        version="1.7.2",
        pipeline_available=pipeline_ok,
        langgraph_available=langgraph_ok,
    )


@router.get("/config", response_model=ConfigResponse)
async def config():
    from smf_swarm.config import get_config

    cfg = get_config()
    return ConfigResponse(
        llm_provider=cfg.llm.provider,
        model=cfg.llm.model,
        base_url=cfg.llm.base_url,
        default_mode=cfg.default_mode,
        default_domain=cfg.default_domain,
        social_agents=cfg.social_agents,
        social_rounds=cfg.social_rounds,
        debate_rounds=cfg.debate_rounds,
        verbose=cfg.verbose,
    )
