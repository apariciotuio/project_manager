"""EP-08 — Celery tasks for notification sweeping.

notifications.sweep_expired:
  - Mark read notifications older than 30 days as 'archived' (sets archived_at).
  - Mark actioned notifications older than 90 days similarly.

Registration: task is auto-discovered. Beat schedule is wired in celery_app.py
when EP-12 ships. For now the task can be triggered manually or via cron.

NOTE: The notifications table does not yet have an archived_at column. This task
sets state='read' for stale unread (30+ days old) to prevent inbox bloat.
A future migration can add archived_at when soft-archiving is needed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.config.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _sweep_expired_notifications() -> dict[str, int]:
    """Mark old unread notifications as read; log stale actioned items."""
    from sqlalchemy import update

    from app.config.settings import get_settings
    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.models.orm import NotificationORM

    get_settings()  # ensure settings loaded before session factory

    now = datetime.now(UTC)
    stale_unread_threshold = now - timedelta(days=30)
    stale_actioned_threshold = now - timedelta(days=90)

    factory = get_session_factory()
    async with factory() as session:
        # Mark unread notifications older than 30 days as read
        unread_stmt = (
            update(NotificationORM)
            .where(
                NotificationORM.state == "unread",
                NotificationORM.created_at < stale_unread_threshold,
            )
            .values(state="read", read_at=now)
            .returning(NotificationORM.id)
        )
        unread_result = await session.execute(unread_stmt)
        unread_count = len(unread_result.all())

        # Log stale actioned notifications (future: set archived_at)
        from sqlalchemy import func, select

        actioned_stmt = (
            select(func.count())
            .select_from(NotificationORM)
            .where(
                NotificationORM.state == "actioned",
                NotificationORM.actioned_at < stale_actioned_threshold,
            )
        )
        actioned_count: int = (await session.execute(actioned_stmt)).scalar_one()

        await session.commit()

    logger.info(
        "notification_sweep: marked %d stale unread as read; "
        "%d stale actioned found (archiving deferred to EP-12)",
        unread_count,
        actioned_count,
    )
    return {"unread_marked_read": unread_count, "actioned_stale": actioned_count}


@celery_app.task(
    name="notifications.sweep_expired",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="default",
)
def sweep_expired_notifications(self):  # type: ignore[no-untyped-def]
    """Celery task: sweep stale notifications.

    - Marks unread > 30 days old as read (inbox hygiene).
    - Logs actioned > 90 days old count (archival deferred to EP-12).

    Beat schedule: register in celery_app.py under EP-12. Until then, trigger
    manually: `celery -A app.worker call notifications.sweep_expired`
    """
    try:
        return asyncio.run(_sweep_expired_notifications())
    except Exception as exc:
        logger.error(
            "notification_sweep: task failed — attempt %d/%d: %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc)
