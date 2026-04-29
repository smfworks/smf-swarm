"""SMF Swarm — Web REST API Routes.

Register Flask blueprints for the web interface.
"""

from __future__ import annotations

import json

from flask import Blueprint, request, jsonify, Response

from smf_swarm.web.jobs import runner
from smf_swarm.web.upload import ingest_file
from smf_swarm.web.auth import require_auth, check_rate_limit

api = Blueprint("api", __name__, url_prefix="/api")

# ─── SSE Helpers ──────────────────────────────────


def _stream_json(data: dict) -> str:
    """Serialize a dict to JSON for SSE."""
    return "data: " + json.dumps(data) + "\n\n"


# ─── Auth decorators ──────────────────────────────


def _check_request():
    """Apply auth and rate limiting to API routes."""
    # Auth
    auth_error = require_auth()
    if auth_error:
        return jsonify(auth_error[0]), auth_error[1]
    # Rate limit by IP
    rate_error = check_rate_limit(request.remote_addr or "unknown")
    if rate_error:
        return jsonify(rate_error[0]), rate_error[1]
    return None


# ─── Routes ───────────────────────────────────────


@api.route("/predict", methods=["POST"])
def predict():
    """Submit a prediction job. Returns job_id."""
    result = _check_request()
    if result:
        return result

    data = request.get_json(force=True) or {}

    query = data.get("query", "").strip()
    mode = data.get("mode", "debate").lower()
    domain = data.get("domain", "general").lower()
    context_text = data.get("context_text", "")

    if not query:
        return jsonify({"error": "Query is required"}), 400
    if mode not in ("standard", "debate", "full"):
        return jsonify({"error": "Mode must be standard, debate, or full"}), 400

    multi_sample = data.get("multi_sample", 1)
    if not isinstance(multi_sample, int) or multi_sample < 1 or multi_sample > 20:
        return (
            jsonify({"error": "multi_sample must be an integer between 1 and 20"}),
            400,
        )

    job_id = runner.submit(
        query=query,
        mode=mode,
        domain=domain,
        context_text=context_text,
        multi_sample=multi_sample,
        langgraph=data.get("langgraph", False),
    )
    return jsonify({"job_id": job_id, "status": "queued"})


@api.route("/predict/langgraph", methods=["POST"])
def predict_langgraph():
    """Submit a prediction job using LangGraph backend."""
    result = _check_request()
    if result:
        return result

    data = request.get_json(force=True) or {}
    query = data.get("query", "").strip()
    mode = data.get("mode", "debate").lower()
    domain = data.get("domain", "general").lower()
    context_text = data.get("context_text", "")

    if not query:
        return jsonify({"error": "Query is required"}), 400
    if mode not in ("standard", "debate", "full"):
        return jsonify({"error": "Mode must be standard, debate, or full"}), 400

    try:
        from smf_swarm.pipeline_langgraph import LANGGRAPH_AVAILABLE

        if not LANGGRAPH_AVAILABLE:
            return (
                jsonify(
                    {
                        "error": "LangGraph not installed. pip install smf-swarm[langgraph]"
                    }
                ),
                503,
            )
    except ImportError:
        return jsonify({"error": "LangGraph not installed"}), 503

    multi_sample = data.get("multi_sample", 1)
    if not isinstance(multi_sample, int) or multi_sample < 1 or multi_sample > 20:
        return (
            jsonify({"error": "multi_sample must be an integer between 1 and 20"}),
            400,
        )

    job_id = runner.submit(
        query=query,
        mode=mode,
        domain=domain,
        context_text=context_text,
        multi_sample=multi_sample,
        langgraph=True,
    )
    return jsonify({"job_id": job_id, "status": "queued", "langgraph": True})


@api.route("/stream/<job_id>")
def stream(job_id: str):
    """SSE endpoint for real-time progress streaming."""
    job = runner.get_job(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        for chunk in runner.event_stream(job_id):
            yield chunk

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@api.route("/status/<job_id>")
def status(job_id: str):
    """Get job status (fallback polling for non-SSE clients)."""
    job = runner.get_job(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404

    payload = {
        "job_id": job.job_id,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "current_node": job.current_node,
        "query": job.query,
        "mode": job.mode,
        "domain": job.domain,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }

    if job.result:
        payload["result"] = runner._result_to_dict(job.result)
    if job.error:
        payload["error"] = job.error

    return jsonify(payload)


@api.route("/upload", methods=["POST"])
def upload():
    """Upload a report/context file (PDF, text, markdown)."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    content = file.read()
    result = ingest_file(content, file.filename)

    return jsonify(result)


@api.route("/config")
def config():
    """Return current pipeline configuration (safe subset)."""
    from smf_swarm.config import get_config

    cfg = get_config()
    return jsonify(
        {
            "llm_provider": cfg.llm.provider,
            "model": cfg.llm.model,
            "default_mode": cfg.default_mode,
            "default_domain": cfg.default_domain,
            "social_agents": cfg.social_agents,
            "social_rounds": cfg.social_rounds,
        }
    )


# ─── Register ─────────────────────────────────────


def register_routes(app):
    """Attach API blueprint to Flask app."""
    app.register_blueprint(api)
