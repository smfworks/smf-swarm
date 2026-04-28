"""SMF Swarm Server — Calibration Router.

POST /api/v1/calibrate — compute conformal intervals on uploaded predictions.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from smf_swarm.server.models import (
    CalibrationRequest,
    CalibrationResponse,
    CalibrationInterval,
)

router = APIRouter(prefix="/calibrate", tags=["calibration"])


def get_auth():
    from smf_swarm.server.auth import AuthManager
    return AuthManager()


def get_ratelimiter():
    from smf_swarm.server.auth import RateLimiter
    return RateLimiter()


@router.post("", response_model=CalibrationResponse)
async def calibrate(req: CalibrationRequest, auth=Depends(get_auth), rl=Depends(get_ratelimiter)):
    confidences = [float(p["confidence"]) for p in req.predictions]
    outcomes = [bool(p["outcome"]) for p in req.predictions]

    try:
        from smf_swarm.conformal import (
            ConformalPredictor,
            coverage_score,
            adaptive_binning,
        )
        cp = ConformalPredictor(alpha=req.alpha)
        cp.fit(confidences, outcomes)
        interval = cp.predict_interval(confidences[0] if confidences else 0.5)
        bins = adaptive_binning(confidences, outcomes, n_bins=5)
        bins_dict = {str(k): v for k, v in bins.items()}
        empirical_cov = coverage_score(cp.intervals) if cp.intervals else None
        return CalibrationResponse(
            empirical_coverage=round(empirical_cov, 4) if empirical_cov is not None else 0.0,
            target_alpha=req.alpha,
            intervals=CalibrationInterval(
                low=round(interval.low, 4),
                high=round(interval.high, 4),
                margin=round(interval.margin, 4),
                coverage=interval.coverage,
                label=interval.label,
            ),
            adaptive_bins=bins_dict,
            recommended_shift=round(cp.recommended_shift, 4) if hasattr(cp, "recommended_shift") else None,
        )
    except ImportError:
        n = len(outcomes)
        empirical_coverage = sum(outcomes) / n if outcomes else 0.0
        margin = 1.96 * (empirical_coverage * (1 - empirical_coverage) / n) ** 0.5 if n > 1 else 0.5
        low = max(0.0, min(1.0, empirical_coverage - margin))
        high = max(0.0, min(1.0, empirical_coverage + margin))
        return CalibrationResponse(
            empirical_coverage=round(empirical_coverage, 4),
            target_alpha=req.alpha,
            intervals=CalibrationInterval(
                low=round(low, 4),
                high=round(high, 4),
                margin=round(margin, 4),
                coverage=1 - req.alpha,
                label="yes" if empirical_coverage > 0.5 else "no",
            ),
        )
