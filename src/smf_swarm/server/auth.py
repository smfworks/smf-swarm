"""SMF Swarm Server — Authorization & Rate Limiting.

Optional Bearer-token middleware and sliding-window per-IP rate limiting.
"""

from __future__ import annotations

import time
from fastapi import Request, HTTPException, status


class AuthManager:
    """Simple bearer-token auth.  token=None means open (dev mode)."""

    def __init__(self, token: str | None = None):
        self._token: str | None = token
        self._enabled: bool = token is not None

    def verify(self, request: Request) -> None:
        if not self._enabled:
            return
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail="Bearer token required"
            )
        provided = auth[7:].strip()
        if provided != self._token:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid token")

    def __call__(self, request: Request) -> None:
        self.verify(request)


class RateLimiter:
    """Sliding-window rate limiter by client IP."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._windows: dict[str, list[float]] = {}

    def check(self, client_ip: str) -> None:
        now = time.time()
        window = self._windows.setdefault(client_ip, [])
        cutoff = now - self._window
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= self._max:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit: {self._max} requests per {self._window}s exceeded",
            )
        window.append(now)

    def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        self.check(client)
