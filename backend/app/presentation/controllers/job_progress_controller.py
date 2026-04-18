"""SSE endpoint for job progress streaming.

GET /api/v1/jobs/{job_id}/progress
  - Auth required
  - 404 when job not found
  - Streams SSE frames from Postgres LISTEN/NOTIFY via SseHandler
  - Sends `: keepalive` comment every 30s of idle time
  - Sends `event: done` when job completes
  - Sends `event: error` when job fails
  - Cleans up LISTEN subscription on client disconnect

Dependency overrides (override_current_user, override_job_progress_service) are
exposed for test injection only. Production code uses the real dependencies.

_stream_job_progress is module-level to allow monkeypatching in integration tests.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infrastructure.sse.job_progress_service import JobProgressService
from app.infrastructure.sse.pg_notification_bus import PgNotificationBus
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


_job_progress_service = JobProgressService()


async def override_job_progress_service() -> JobProgressService:
    """Default dependency — returns the process-singleton in-memory job progress service.

    Tests inject a fresh instance via dependency_overrides to ensure isolation.
    """
    return _job_progress_service


# ---------------------------------------------------------------------------
# SSE streaming (module-level for monkeypatching in tests)
# ---------------------------------------------------------------------------


async def _stream_job_progress(
    job_id: str,
    db_dsn: str,
    keepalive_interval: float = _KEEPALIVE_INTERVAL,
) -> AsyncGenerator[str]:
    """Build a SseHandler backed by PgNotificationBus and stream job progress."""
    bus = PgNotificationBus(dsn=db_dsn)
    handler = SseHandler(bus, keepalive_interval=keepalive_interval)
    channel = f"{_SSE_CHANNEL_PREFIX}{job_id}"
    async for frame in handler._generate(channel):
        yield frame


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
    """Stream SSE events for a long-running job.

    Returns 401 when no valid auth token is present (enforced by dependency).
    Returns 404 when job_id is unknown.
    """
    state = await job_svc.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND"}})

    from app.config.settings import get_settings

    # Strip SQLAlchemy dialect prefix — asyncpg DSN uses plain postgresql://
    db_url = get_settings().database.url.replace("postgresql+asyncpg://", "postgresql://")

    return StreamingResponse(
        _stream_job_progress(job_id, db_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
