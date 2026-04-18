"""EP-00 Phase 9 — periodic cleanup of expired session rows.

Plain async function — no Celery. Triggered via:
  POST /api/v1/internal/jobs/cleanup_expired_sessions/run (superadmin)
Host cron hits that endpoint daily at 03:15 UTC.

Deletes every row where `expires_at < NOW()`. Active sessions are left alone;
revoked-but-still-within-TTL rows are kept so recent logouts stay queryable
for audit correlation.
"""

from __future__ import annotations

import logging

from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.session_repository_impl import SessionRepositoryImpl

logger = logging.getLogger(__name__)


async def cleanup_expired_sessions() -> int:
    factory = get_session_factory()
    async with factory() as session:
        repo = SessionRepositoryImpl(session)
        deleted = await repo.delete_expired()
        await session.commit()
    logger.info("cleanup_expired_sessions removed %d rows", deleted)
    return deleted
