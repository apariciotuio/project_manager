"""EP-00 Phase 9 — periodic cleanup of expired `oauth_states` rows.

Plain async function — no Celery. Triggered via:
  POST /api/v1/internal/jobs/cleanup_expired_oauth_states/run (superadmin)
Host cron hits that endpoint every 10 minutes.

The table would bloat otherwise because `consume()` only deletes the row that
matched — expired rows that the user abandoned mid-flow stay until this job
sweeps them.
"""

from __future__ import annotations

import logging

from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.oauth_state_repository_impl import (
    OAuthStateRepositoryImpl,
)

logger = logging.getLogger(__name__)


async def cleanup_expired_oauth_states() -> int:
    factory = get_session_factory()
    async with factory() as session:
        repo = OAuthStateRepositoryImpl(session)
        deleted = await repo.cleanup_expired()
        await session.commit()
    logger.info("cleanup_expired_oauth_states removed %d rows", deleted)
    return deleted
