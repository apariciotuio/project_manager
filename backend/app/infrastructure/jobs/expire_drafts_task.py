"""EP-02 Phase 7 — periodic cleanup of expired pre-creation draft rows.

Runs daily at 02:00 UTC via Celery Beat. Deletes every row where
`expires_at < NOW()`. Active drafts are left untouched.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config.celery_app import celery_app
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.work_item_draft_repository_impl import (
    WorkItemDraftRepositoryImpl,
)
from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl

logger = logging.getLogger(__name__)


async def _run() -> int:
    from app.application.services.draft_service import DraftService

    factory = get_session_factory()
    async with factory() as session:
        draft_repo = WorkItemDraftRepositoryImpl(session)
        work_item_repo = WorkItemRepositoryImpl(session)
        service = DraftService(draft_repo=draft_repo, work_item_repo=work_item_repo)
        deleted = await service.expire_pre_creation_drafts()
        await session.commit()
    return deleted


def _run_sync() -> int:
    def _worker() -> int:
        return asyncio.run(_run())

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.infrastructure.jobs.expire_drafts_task.expire_work_item_drafts"
)
def expire_work_item_drafts() -> int:
    deleted = _run_sync()
    logger.info("expire_work_item_drafts removed %d rows", deleted)
    return deleted
