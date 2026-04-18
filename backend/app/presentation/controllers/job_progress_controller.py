"""SSE endpoint for Celery job progress streaming.

GET /api/v1/jobs/{job_id}/progress
  - Auth required
  - 404 when job not found (or not owned — we use the job_id UUID as the auth check)
  - Streams SSE frames from Redis pub/sub channel
  - Sends `: keepalive` comment every 30s of idle time
  - Sends `event: done` when Celery task completes
  - Sends `event: error` when Celery task fails
  - Cleans up Redis subscription on client disconnect

Dependency overrides (override_current_user, override_job_progress_service) are
exposed for test injection only. Production code uses the real dependencies.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infrastructure.sse.job_progress_service import JobProgressService
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter()

_KEEPALIVE_INTERVAL = 30.0  # seconds
_SSE_CHANNEL_PREFIX = "sse:job:"


# ---------------------------------------------------------------------------
# Dependency factories (overridable in tests)
# ---------------------------------------------------------------------------


async def override_current_user(request: Request) -> CurrentUser:
    """Real auth dependency — defers import to avoid circular dependency at module load."""
    from app.presentation.dependencies import get_current_user

    return await get_current_user(request)


async def override_job_progress_service() -> JobProgressService:
    """Default dependency — creates a per-request JobProgressService backed by Redis."""
    from app.config.settings import get_settings

    settings = get_settings()
    client = aioredis.from_url(settings.redis.url, decode_responses=True)
    return JobProgressService(client)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SSE frame helpers
# ---------------------------------------------------------------------------


def _sse_data(event_type: str | None, data: dict[str, Any]) -> str:
    lines = []
    if event_type:
        lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # blank line terminator
    lines.append("")
    return "\n".join(lines)


def _sse_keepalive() -> str:
    return ": keepalive\n\n"


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _stream_job_progress(
    job_id: str,
    redis_url: str,
    keepalive_interval: float = _KEEPALIVE_INTERVAL,
) -> AsyncGenerator[str]:
    client = aioredis.from_url(redis_url, decode_responses=True)
    pubsub_obj = client.pubsub()
    channel = f"{_SSE_CHANNEL_PREFIX}{job_id}"

    await pubsub_obj.subscribe(channel)
    last_event_time = asyncio.get_event_loop().time()

    try:
        while True:
            now = asyncio.get_event_loop().time()
            elapsed = now - last_event_time

            if elapsed >= keepalive_interval:
                yield _sse_keepalive()
                last_event_time = now

            msg = await pubsub_obj.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if msg is not None and msg.get("type") == "message":
                raw = msg["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()
                try:
                    event = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue

                event_type = event.get("type")

                if event_type == "done":
                    yield _sse_data("done", event.get("payload", event))
                    return
                elif event_type == "error":
                    yield _sse_data("error", event.get("payload", event))
                    return
                else:
                    yield _sse_data(None, event)
                    last_event_time = asyncio.get_event_loop().time()
            else:
                await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        logger.debug("SSE client disconnected for job %s", job_id)
    finally:
        await pubsub_obj.unsubscribe(channel)
        await pubsub_obj.close()
        await client.aclose()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}/progress")
async def job_progress(
    job_id: str,
    _request: Request,
    _current_user: CurrentUser = Depends(override_current_user),
    job_svc: JobProgressService = Depends(override_job_progress_service),
) -> StreamingResponse:
    """Stream SSE events for a long-running Celery job.

    Returns 401 when no valid auth token is present (enforced by dependency).
    Returns 404 when job_id is unknown.
    """
    state = await job_svc.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND"}})

    from app.config.settings import get_settings

    redis_url = get_settings().redis.url

    return StreamingResponse(
        _stream_job_progress(job_id, redis_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
