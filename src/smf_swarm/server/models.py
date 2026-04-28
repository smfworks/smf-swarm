"""SMF Swarm Server — Pydantic Request/Response Models.

Shared data models for FastAPI request validation and response serialization.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unhealthy"] = "ok"
    version: str
    pipeline_available: bool = True
    langgraph_available: bool = False


class PredictRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000, description="Prediction question")
    mode: Literal["standard", "debate", "full"] = "debate"
    domain: str = "general"
    context_text: str = Field("", max_length=50000, description="Additional context text")
    multi_sample: int = Field(1, ge=1, le=20, description="Number of temperature-swept runs")
    langgraph: bool = Field(False, description="Use LangGraph backend if installed")
    output_confidence_interval: bool = Field(True, description="Include calibrated confidence interval in response")
    conformal_alpha: float = Field(0.05, gt=0.0, lt=1.0)

    @field_validator("domain")
    @classmethod
    def _domain_lowercase(cls, v):
        return v.strip().lower()


class PredictResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_s: Optional[float] = None


class BatchItem(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    mode: Literal["standard", "debate", "full"] = "debate"
    domain: str = "general"
    context_text: str = ""
    multi_sample: int = 1


class BatchRequest(BaseModel):
    items: list[BatchItem] = Field(..., min_length=1, max_length=100, description="Up to 100 prediction items")

    @field_validator("items")
    @classmethod
    def _items_len(cls, v):
        if len(v) > 100:
            raise ValueError("Batch size cannot exceed 100")
        return v


class BatchResponse(BaseModel):
    batch_id: str
    status: Literal["queued", "running", "completed", "failed"]
    total: int
    completed: int
    failed: int
    results: list[dict]
    duration_s: Optional[float] = None
    completed_at: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress_pct: int = 0
    current_node: Optional[str] = None
    query: Optional[str] = None
    mode: Optional[str] = None
    domain: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    duration_s: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class BenchmarkRequest(BaseModel):
    dataset: str = Field(..., min_length=1, description="Dataset name or filepath")
    modes: list[Literal["standard", "debate", "full"]] = ["standard", "debate", "full"]
    multi_samples: list[int] = [1, 5]
    output_dir: str = "benchmark_results"
    llm_model: str = ""


class BenchmarkResponse(BaseModel):
    batch_id: str
    status: Literal["queued", "running", "completed", "failed"]
    total: int
    completed: int
    metrics: Optional[dict] = None


class CalibrationRequest(BaseModel):
    predictions: list[dict] = Field(..., min_length=2, description="List of {confidence, outcome} records")
    alpha: float = Field(0.05, gt=0.0, lt=1.0, description="Target miscoverage rate (default 0.05 = 95%)")

    @field_validator("predictions")
    @classmethod
    def _validate_predictions(cls, v):
        for i, p in enumerate(v):
            if "confidence" not in p or "outcome" not in p:
                raise ValueError(f"Prediction {i} must have 'confidence' and 'outcome' keys")
            if not (0.0 <= p["confidence"] <= 1.0):
                raise ValueError(f"Prediction {i} confidence must be in [0,1]")
            if p["outcome"] not in (0, 1, True, False):
                raise ValueError(f"Prediction {i} outcome must be 0/1 or True/False")
        return v


class CalibrationInterval(BaseModel):
    low: float
    high: float
    margin: float
    coverage: float
    label: str


class CalibrationResponse(BaseModel):
    empirical_coverage: float
    target_alpha: float
    intervals: Optional[CalibrationInterval] = None
    adaptive_bins: Optional[dict] = None
    recommended_shift: Optional[float] = None


class ConfigResponse(BaseModel):
    llm_provider: str
    model: str
    base_url: str
    default_mode: str
    default_domain: str
    social_agents: int
    social_rounds: int
    debate_rounds: int
    verbose: bool


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
