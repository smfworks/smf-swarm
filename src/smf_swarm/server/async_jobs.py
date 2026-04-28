"""SMF Swarm Server — Async SSE Streaming.

Wraps the sync JobRunner event stream in an async generator for FastAPI.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from smf_swarm.server.runner import get_runner


def to_sse_event(data: dict) -> str:
    return "data: " + json.dumps(data) + "\n\n"


async def event_stream(job_id: str) -> AsyncGenerator[str, None]:
    runner = get_runner()
    job = runner.get_job(job_id)
    if job is None:
        yield to_sse_event({"type": "error", "message": "Job not found"})
        return

    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()

    def consume():
        import queue as q_std
        for raw in runner.event_stream(job_id):
            try:
                if raw.startswith("event: "):
                    lines = raw.strip().split("\n")
                    ev_type = lines[0][7:]
                    data_line = lines[1] if len(lines) > 1 else ""
                    payload = json.loads(data_line[6:]) if data_line.startswith("data: ") else {}
                    payload["_event_type"] = ev_type
                elif raw.startswith("data: "):
                    payload = json.loads(raw[6:])
                else:
                    payload = {"type": "log", "message": raw.strip()}
            except Exception:
                payload = {"type": "log", "message": raw.strip()}
            asyncio.run_coroutine_threadsafe(q.put(payload), loop)
        asyncio.run_coroutine_threadsafe(q.put(None), loop)

    import threading
    t = threading.Thread(target=consume, daemon=True)
    t.start()

    while True:
        payload = await q.get()
        if payload is None:
            break
        yield to_sse_event(payload)
        if payload.get("type") in ("result", "error"):
            break
