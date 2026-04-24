"""SMF Swarm — Structured output extraction using Pydantic schemas.

Replaces fragile regex parsing with Pydantic-validated JSON outputs
via LangChain's with_structured_output or manual JSON parsing with fallbacks.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Type
from pydantic import BaseModel, Field


# ─── Schemas ────────────────────────────────────

class ConfidenceOutput(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(default="", description="Brief reasoning for the confidence score")


class DataQualityOutput(BaseModel):
    data_quality_score: float = Field(..., ge=0.0, le=1.0, description="Quality of data sources")
    key_sources: list[str] = Field(default_factory=list, description="Named data sources")


class ValidationOutput(BaseModel):
    passed: bool = Field(..., description="Whether the prediction passes validation")
    issues: list[str] = Field(default_factory=list, description="List of issues found")


class FeatureOutput(BaseModel):
    feature_count: int = Field(..., ge=1, description="Number of predictive features identified")
    top_features: list[str] = Field(default_factory=list, description="Names of top features")


class ReportSectionsOutput(BaseModel):
    executive_summary: str = Field(default="", description="Concise 1-paragraph summary")
    full_prediction: str = Field(default="", description="Detailed prediction")
    risk_assessment: str = Field(default="", description="Key risks and caveats")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SentimentOutput(BaseModel):
    sentiment: float = Field(default=0.0, ge=-1.0, le=1.0, description="Sentiment from -1 (bearish) to +1 (bullish)")
    keywords: list[str] = Field(default_factory=list)


# ─── Extraction helpers ─────────────────────────

def _extract_json_block(text: str) -> Optional[str]:
    """Pull the first JSON object/array from Markdown or raw text."""
    # Try fenced code block first
    fenced = re.search(r'```(?:json)?\s*\n((?:\{.*?\}|\[.*?\])\s*)\n```', text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # Try raw JSON object
    raw = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', text, re.DOTALL)
    if raw:
        return raw.group(1).strip()
    return None


def parse_structured(text: str, schema: Type[BaseModel]) -> Optional[BaseModel]:
    """Parse LLM output into a Pydantic model with fallback regex extraction."""
    json_str = _extract_json_block(text)
    if json_str:
        try:
            data = json.loads(json_str)
            return schema(**data)
        except (json.JSONDecodeError, Exception):
            pass
    return None


def extract_confidence(text: str) -> float:
    """Extract confidence using structured JSON first, then regex fallback."""
    parsed = parse_structured(text, ConfidenceOutput)
    if parsed:
        return parsed.confidence
    # Fallback: last-match regex (original behavior, hardened)
    text = text.replace("*", "")
    matches = re.findall(r'CONFIDENCE[:\\s]+([0-9]*\\.?[0-9]+)', text, re.I)
    if matches:
        return min(1.0, max(0.0, float(matches[-1])))
    return 0.5


def extract_data_quality(text: str) -> float:
    parsed = parse_structured(text, DataQualityOutput)
    if parsed:
        return parsed.data_quality_score
    m = re.search(r'DATA_QUALITY_SCORE[:\\s]*([0-9]*\\.?[0-9]+)', text, re.I)
    if m:
        return min(1.0, max(0.0, float(m.group(1))))
    return 0.5


def extract_feature_count(text: str) -> int:
    parsed = parse_structured(text, FeatureOutput)
    if parsed:
        return parsed.feature_count
    m = re.search(r'FEATURE_COUNT[:\\s]*(\\d+)', text, re.I)
    if m:
        return int(m.group(1))
    return 5


def extract_validation(text: str) -> bool:
    parsed = parse_structured(text, ValidationOutput)
    if parsed:
        return parsed.passed
    return "PASS" in text.upper()[-200:]


def extract_report_sections(text: str) -> dict:
    parsed = parse_structured(text, ReportSectionsOutput)
    if parsed:
        return {
            "executive_summary": parsed.executive_summary or text[:300],
            "full_prediction": parsed.full_prediction,
            "risk_assessment": parsed.risk_assessment or "See prediction for risks",
            "confidence": parsed.confidence,
        }
    # Legacy regex fallback
    lines = text.split("\n")
    summary = ""
    risk = ""
    buf = []
    capture = None
    for line in lines:
        u = line.upper().strip()
        if "EXECUTIVE_SUMMARY" in u or "EXECUTIVE SUMMARY" in u:
            capture = "summary"
            buf = [line.split(":", 1)[1].strip()] if ":" in line else []
            continue
        elif "FULL_PREDICTION" in u:
            if capture == "summary":
                summary = " ".join(buf[:20])
            capture = None
            continue
        elif "RISK_ASSESSMENT" in u or "RISK ASSESSMENT" in u:
            capture = "risk"
            buf = [line.split(":", 1)[1].strip()] if ":" in line else []
            continue
        elif capture and line.strip() and not line.strip().startswith("*"):
            buf.append(line.strip())
    if capture == "risk":
        risk = " ".join(buf[:20])
    return {
        "executive_summary": summary or text[:300],
        "full_prediction": "",
        "risk_assessment": risk or "See prediction for risks",
        "confidence": 0.5,
    }


# ─── Sentiment extraction (replaces keyword counting) ─

def extract_sentiment(text: str) -> float:
    """Extract sentiment score from text using structured JSON first, then keyword heuristic."""
    parsed = parse_structured(text, SentimentOutput)
    if parsed:
        return max(-1.0, min(1.0, parsed.sentiment))
    # Fallback keyword heuristic (aligned with original but improved)
    text = text.lower()
    bullish = ["likely", "yes", "growth", "surge", "exceed", "accelerate", "bullish", "optimistic", "confident"]
    bearish = ["unlikely", "no", "decline", "fall", "below", "risk", "bearish", "pessimistic", "concerned"]
    b = sum(1 for w in bullish if w in text)
    c = sum(1 for w in bearish if w in text)
    if b + c == 0:
        return 0.0
    return round((b - c) / max(b + c, 1), 2)
