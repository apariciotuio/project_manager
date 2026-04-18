"""Mixin that publishes SSE progress frames via Postgres NOTIFY (PgNotificationBus).

ProgressTaskMixin provides three async helpers:
  publish_progress(job_id, pct) — fire-and-forget progress frame (no state write)
  publish_done(job_id, message_id) — terminal frame + JobProgressService.complete()
  publish_error(job_id, error_msg) — terminal frame + JobProgressService.fail()

Channel: always sse:job:{job_id} (ChannelRegistry.job convention).

Usage:

    from app.infrastructure.tasks.progress_task import ProgressTaskMixin
    from app.infrastructure.sse.pg_notification_bus import PgNotificationBus

    async def _run(job_id: str, ...) -> None:
        bus = PgNotificationBus(dsn=dsn)
        mixin = ProgressTaskMixin(publisher=bus, job_service=job_svc)
        await mixin.publish_progress(job_id, pct=30)
        ...
        await mixin.publish_done(job_id, message_id="msg-uuid")
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.infrastructure.sse.channel_registry import ChannelRegistry
from app.infrastructure.sse.job_progress_service import JobProgressService

logger = logging.getLogger(__name__)

_SSE_JOB_PREFIX = "sse:job:"


class _PublishProto(Protocol):
    async def publish(self, channel: str, message: dict[str, Any]) -> None: ...


class ProgressTaskMixin:
    """Async helpers for publishing SSE frames via PgNotificationBus (or compatible).

    Args:
        publisher: PgNotificationBus instance (or any object satisfying _PublishProto).
        job_service: Optional JobProgressService for persistent state updates.
                     When omitted, publish_done / publish_error skip state writes.
    """

    def __init__(
        self,
        publisher: _PublishProto,
        job_service: JobProgressService | None = None,
    ) -> None:
        self._publisher = publisher
        self._job_service = job_service
        self._registry = ChannelRegistry()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _channel(self, job_id: str) -> str:
        return self._registry.job(job_id)

    async def _publish_raw(self, channel: str, payload: dict[str, Any]) -> None:
        await self._publisher.publish(channel, payload)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish_progress(self, job_id: str, *, pct: int) -> None:
        """Publish a progress frame.  No persistent state write — hot path."""
        channel = self._channel(job_id)
        await self._publish_raw(
            channel,
            {"type": "progress", "payload": {"pct": pct}},
        )
        logger.debug("progress job=%s pct=%d", job_id, pct)

    async def publish_done(self, job_id: str, *, message_id: str) -> None:
        """Publish terminal done frame and update persistent job state."""
        channel = self._channel(job_id)
        await self._publish_raw(
            channel,
            {"type": "done", "payload": {"message_id": message_id}},
        )
        if self._job_service is not None:
            await self._job_service.complete(job_id, message_id)
        logger.info("done job=%s message_id=%s", job_id, message_id)

    async def publish_error(self, job_id: str, *, error_msg: str) -> None:
        """Publish terminal error frame and update persistent job state."""
        channel = self._channel(job_id)
        await self._publish_raw(
            channel,
            {"type": "error", "payload": {"message": error_msg}},
        )
        if self._job_service is not None:
            await self._job_service.fail(job_id, error_msg)
        logger.error("error job=%s error=%s", job_id, error_msg)
