"""Tests for the SMF Swarm FastAPI server.

Uses FastAPI TestClient for synchronous request/response testing.
To run:
    pytest tests/test_server.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from smf_swarm.server.app import create_app


@pytest.fixture
def client():
    """FastAPI TestClient with no auth/rate limit."""
    app = create_app(token=None, rate_limit=None)
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.7.2"
        assert data["pipeline_available"] is True
        assert isinstance(data["langgraph_available"], bool)


class TestConfig:
    def test_config_sanitized(self, client):
        res = client.get("/api/v1/config")
        assert res.status_code == 200
        data = res.json()
        assert "llm_provider" in data
        assert "model" in data
        assert "api_key" not in data


class TestPredictAsync:
    def test_predict_basic(self, client):
        payload = {"query": "Will it rain tomorrow?", "mode": "debate"}
        res = client.post("/api/v1/predict", json=payload)
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "queued"
        assert data["job_id"].startswith("smf-")

    def test_predict_missing_query(self, client):
        res = client.post("/api/v1/predict", json={"mode": "debate"})
        assert res.status_code == 422

    def test_predict_invalid_mode(self, client):
        res = client.post("/api/v1/predict", json={"query": "Test", "mode": "invalid"})
        assert res.status_code == 422

    def test_predict_multi_sample_bounds(self, client):
        res = client.post("/api/v1/predict", json={"query": "Test", "multi_sample": 25})
        assert res.status_code == 422

    def test_predict_alpha_bounds(self, client):
        res = client.post(
            "/api/v1/predict", json={"query": "Test", "conformal_alpha": -0.1}
        )
        assert res.status_code == 422


class TestJobs:
    def test_get_job_not_found(self, client):
        res = client.get("/api/v1/jobs/fake-job-id")
        assert res.status_code == 404

    def test_list_jobs(self, client):
        client.post("/api/v1/predict", json={"query": "Test"})
        res = client.get("/api/v1/jobs")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert "jobs" in data

    def test_cancel_job_not_found(self, client):
        res = client.delete("/api/v1/jobs/nonexistent")
        assert res.status_code == 404


class TestBatch:
    def test_batch_basic(self, client):
        payload = {
            "items": [
                {"query": "Q1", "mode": "standard"},
                {"query": "Q2", "mode": "debate"},
            ]
        }
        res = client.post("/api/v1/batch", json=payload)
        assert res.status_code == 202
        data = res.json()
        assert data["batch_id"].startswith("batch-")
        assert data["total"] == 2
        assert data["status"] == "queued"

    def test_batch_empty(self, client):
        res = client.post("/api/v1/batch", json={"items": []})
        assert res.status_code == 422

    def test_batch_exceeds_max(self, client):
        payload = {"items": [{"query": "Q"} for _ in range(101)]}
        res = client.post("/api/v1/batch", json=payload)
        assert res.status_code == 422

    def test_get_batch_not_found(self, client):
        res = client.get("/api/v1/batch/nonexistent")
        assert res.status_code == 404


class TestCalibration:
    def test_calibration_basic(self, client):
        payload = {
            "predictions": [
                {"confidence": 0.72, "outcome": True},
                {"confidence": 0.45, "outcome": False},
                {"confidence": 0.88, "outcome": True},
                {"confidence": 0.60, "outcome": False},
                {"confidence": 0.75, "outcome": True},
            ],
            "alpha": 0.1,
        }
        res = client.post("/api/v1/calibrate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "empirical_coverage" in data
        assert data["target_alpha"] == 0.1
        iv = data["intervals"]
        assert 0.0 <= iv["low"] <= 1.0
        assert 0.0 <= iv["high"] <= 1.0
        assert iv["margin"] >= 0

    def test_calibration_missing_field(self, client):
        payload = {"predictions": [{"confidence": 0.5}]}
        res = client.post("/api/v1/calibrate", json=payload)
        assert res.status_code == 422

    def test_calibration_empty(self, client):
        payload = {"predictions": []}
        res = client.post("/api/v1/calibrate", json=payload)
        assert res.status_code == 422


class TestBenchmark:
    def test_benchmark_queue(self, client):
        payload = {"dataset": "dummy", "modes": ["standard"], "multi_samples": [1]}
        res = client.post("/api/v1/benchmark", json=payload)
        assert res.status_code == 202
        data = res.json()
        assert data["batch_id"].startswith("bench-")
        assert data["status"] == "queued"

    def test_get_benchmark_not_found(self, client):
        res = client.get("/api/v1/benchmark/nonexistent")
        assert res.status_code == 404


class TestRateLimit:
    def test_rate_limit_respected(self, client):
        app = create_app(token=None, rate_limit=(5, 60))
        with TestClient(app) as cl:
            for i in range(5):
                res = cl.post("/api/v1/predict", json={"query": f"Q{i}"})
                assert res.status_code in (202, 429), f"Loop {i}: got {res.status_code}"


class TestJSONSchema:
    def test_all_responses_are_json(self, client):
        res = client.get("/api/v1/health")
        assert res.headers["content-type"].startswith("application/json")
        res = client.get("/api/v1/config")
        assert res.headers["content-type"].startswith("application/json")
