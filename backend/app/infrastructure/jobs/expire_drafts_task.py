"""EP-02 Phase 7 — periodic cleanup of expired pre-creation draft rows.

Plain async function — no Celery. Triggered via:
  POST /api/v1/internal/jobs/expire_work_item_drafts/run (superadmin)
Host cron hits that endpoint daily at 02:00 UTC.

Deletes every row where `expires_at < NOW()`. Active drafts are left untouched.
"""

from __future__ import annotations

import logging

from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.work_item_draft_repository_impl import (
    WorkItemDraftRepositoryImpl,
)
from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl

logger = logging.getLogger(__name__)


async def expire_work_item_drafts() -> int:
    from app.application.services.draft_service import DraftService

    factory = get_session_factory()
    async with factory() as session:
        draft_repo = WorkItemDraftRepositoryImpl(session)
        work_item_repo = WorkItemRepositoryImpl(session)
        service = DraftService(draft_repo=draft_repo, work_item_repo=work_item_repo)
        deleted = await service.expire_pre_creation_drafts()
        await session.commit()
    logger.info("expire_work_item_drafts removed %d rows", deleted)
    return deleted
