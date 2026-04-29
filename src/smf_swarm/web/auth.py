"""SMF Swarm — Web auth and rate limiting utilities.

Lightweight bearer-token auth and in-memory rate limiting.
No external dependencies beyond Flask.
"""

from __future__ import annotations

import time
from typing import Optional

from flask import request


class RateLimiter:
    """Simple in-memory sliding-window rate limiter per IP."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._log: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        timestamps = self._log.get(key, [])
        # Trim old entries
        timestamps = [t for t in timestamps if now - t < self.window]
        if len(timestamps) >= self.max_requests:
            self._log[key] = timestamps
            return False
        timestamps.append(now)
        self._log[key] = timestamps
        return True


_rate_limiter: Optional[RateLimiter] = None
_auth_token: Optional[str] = None


def init_auth(
    token: Optional[str] = None, rate_limit: Optional[tuple[int, int]] = None
):
    """Initialize web auth and rate limiting.

    Args:
        token: Bearer token string. If set, all API requests require Authorization header.
        rate_limit: (max_requests, window_seconds) tuple. e.g. (10, 60) for 10 req/min.
    """
    global _auth_token, _rate_limiter
    _auth_token = token
    if rate_limit:
        _rate_limiter = RateLimiter(*rate_limit)


def require_auth() -> Optional[tuple]:
    """Check bearer token if one is configured. Returns error response tuple or None."""
    if _auth_token is None:
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized — Authorization: Bearer <token> required"}, 401
    provided = auth_header.split("Bearer ", 1)[1].strip()
    if provided != _auth_token:
        return {"error": "Invalid token"}, 403
    return None


def check_rate_limit(key: str) -> Optional[tuple]:
    """Check rate limit if enabled. Returns error response tuple or None."""
    if _rate_limiter is None:
        return None
    if not _rate_limiter.is_allowed(key):
        return {
            "error": f"Rate limit exceeded — {_rate_limiter.max_requests} requests per {_rate_limiter.window}s"
        }, 429
    return None
