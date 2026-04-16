"""EP-00 Phase 9 — periodic cleanup of expired session rows.

Runs daily via Celery Beat. Deletes every row where `expires_at < NOW()`. Active
sessions are left alone; revoked-but-still-within-TTL rows are kept so recent
logouts stay queryable for audit correlation.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config.celery_app import celery_app
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.session_repository_impl import SessionRepositoryImpl

logger = logging.getLogger(__name__)


async def _run() -> int:
    factory = get_session_factory()
    async with factory() as session:
        repo = SessionRepositoryImpl(session)
        deleted = await repo.delete_expired()
        await session.commit()
    return deleted


def _run_sync() -> int:
    # A dedicated thread keeps the task callable from both sync Celery workers
    # and from pytest-asyncio contexts where the default loop is already running.
    def _worker() -> int:
        return asyncio.run(_run())

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result()


@celery_app.task(  # type: ignore[misc]
    name="app.infrastructure.jobs.session_cleanup.cleanup_expired_sessions"
)
def cleanup_expired_sessions() -> int:
    deleted = _run_sync()
    logger.info("cleanup_expired_sessions removed %d rows", deleted)
    return deleted
