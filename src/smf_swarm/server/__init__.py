"""SMF Swarm — FastAPI Server Module.

HTTP API for headless prediction, benchmarking, calibration, and job status.

Usage:
    uvicorn smf_swarm.server:create_app --factory --host 0.0.0.0 --port 8080
    # or
    from smf_swarm.server import create_app
    app = create_app()
"""

from smf_swarm.server.app import create_app

__all__ = ["create_app"]
