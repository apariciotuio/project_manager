"""EP-00 Phase 9 — periodic cleanup of expired `oauth_states` rows.

Runs every 10 minutes via Celery Beat. The table would bloat otherwise because
`consume()` only deletes the row that matched — expired rows that the user
abandoned mid-flow stay until this job sweeps them.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config.celery_app import celery_app
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.oauth_state_repository_impl import (
    OAuthStateRepositoryImpl,
)

logger = logging.getLogger(__name__)


async def _run() -> int:
    factory = get_session_factory()
    async with factory() as session:
        repo = OAuthStateRepositoryImpl(session)
        deleted = await repo.cleanup_expired()
        await session.commit()
    return deleted


def _run_sync() -> int:
    def _worker() -> int:
        return asyncio.run(_run())

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result()


@celery_app.task(  # type: ignore[misc]
    name="app.infrastructure.jobs.oauth_state_cleanup.cleanup_expired_oauth_states"
)
def cleanup_expired_oauth_states() -> int:
    deleted = _run_sync()
    logger.info("cleanup_expired_oauth_states removed %d rows", deleted)
    return deleted
