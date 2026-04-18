"""SSE endpoint for Celery job progress streaming.

GET /api/v1/jobs/{job_id}/progress
  - Auth required
  - 404 when job not found (or not owned — we use the job_id UUID as the auth check)
  - Streams SSE frames from Redis pub/sub channel via SseHandler
  - Sends `: keepalive` comment every 30s of idle time
  - Sends `event: done` when Celery task completes
  - Sends `event: error` when Celery task fails
  - Cleans up Redis subscription on client disconnect

Dependency overrides (override_current_user, override_job_progress_service) are
exposed for test injection only. Production code uses the real dependencies.

_stream_job_progress is module-level to allow monkeypatching in integration tests.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infrastructure.sse.job_progress_service import JobProgressService
from app.infrastructure.sse.redis_pubsub import RedisPubSub
from app.infrastructure.sse.sse_handler import SseHandler
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
# SSE streaming (module-level for monkeypatching in tests)
# ---------------------------------------------------------------------------


async def _stream_job_progress(
    job_id: str,
    redis_url: str,
    keepalive_interval: float = _KEEPALIVE_INTERVAL,
) -> AsyncGenerator[str]:
    """Build a SseHandler backed by a per-request Redis client and stream job progress."""
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        pubsub = RedisPubSub(client)  # type: ignore[arg-type]
        handler = SseHandler(pubsub, keepalive_interval=keepalive_interval)  # type: ignore[arg-type]
        channel = f"{_SSE_CHANNEL_PREFIX}{job_id}"
        # Delegate to SseHandler generator — yields SSE frames
        async for frame in handler._generate(channel):
            yield frame
    finally:
        await client.aclose()  # type: ignore[attr-defined]


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
