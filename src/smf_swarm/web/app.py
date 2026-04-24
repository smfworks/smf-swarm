"""SMF Swarm — Web Flask Application.

Boots a standalone web UI for casual users to run predictions via browser.
"""

from __future__ import annotations

import os
import sys

from flask import Flask, Response, send_from_directory

from smf_swarm.web.api import api


def create_app() -> Flask:
    """Factory: create and configure the Flask app."""
    here = os.path.dirname(os.path.abspath(__file__))
    static_folder = os.path.join(here, "static")

    app = Flask(
        __name__,
        static_folder=static_folder,
        static_url_path="",
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB uploads

    # Register API blueprint first so /api/* has priority
    app.register_blueprint(api)

    # SPA catch-all: serve index.html for non-API, non-static routes
    @app.route("/health")
    def health():
        return {"status": "ok", "version": "1.3.0"}

    @app.route("/")
    def index():
        return send_from_directory(static_folder, "index.html")

    @app.route("/<path:path>")
    def spa_catchall(path):
        # if static file exists, serve it; otherwise serve index.html for SPA routing
        static_path = os.path.join(static_folder, path)
        if os.path.isfile(static_path):
            return send_from_directory(static_folder, path)
        return send_from_directory(static_folder, "index.html")

    return app


def run_server(host: str = "127.0.0.1", port: int = 8080, debug: bool = False, auth_token: str | None = None, rate_limit: tuple[int, int] | None = None):
    """Print banner and start server."""
    from smf_swarm.web.auth import init_auth
    init_auth(token=auth_token, rate_limit=rate_limit)

    app = create_app()

    url = f"http://{host}:{port}"
    print("\n  SMF Swarm Web UI")
    print("  " + "━" * 52)
    print(f"  Server:   {url}")
    if auth_token:
        print(f"  Auth:     Bearer token required")
    if rate_limit:
        print(f"  Rate:     {rate_limit[0]} req / {rate_limit[1]}s")
    if host == "0.0.0.0":
        print("  ⚠ WARNING: Binding to 0.0.0.0 exposes this server to the network.")
        if not auth_token:
            print("  ⚠ WARNING: No auth token set. Anyone on your network can access this.")
    print(f"  Press Ctrl+C to stop")
    print("  " + "━" * 52 + "\n")
    sys.stdout.flush()

    try:
        app.run(host=host, port=port, debug=debug, threaded=True)
    except KeyboardInterrupt:
        print("\n\n  Server stopped.")
        sys.exit(0)
