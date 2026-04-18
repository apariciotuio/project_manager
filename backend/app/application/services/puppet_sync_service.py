"""EP-13 — PuppetSyncService.

Enqueues index/delete operations into the puppet_sync_outbox table. The Celery
drain_puppet_outbox task reads the outbox and calls PuppetClient.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.infrastructure.persistence.puppet_outbox_repository_impl import (
    PuppetOutboxRepositoryImpl,
)

logger = logging.getLogger(__name__)


class PuppetSyncService:
    def __init__(self, outbox_repo: PuppetOutboxRepositoryImpl) -> None:
        self._outbox = outbox_repo

    async def enqueue_index(
        self,
        workspace_id: UUID,
        work_item_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        await self._outbox.enqueue(
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            operation="index",
            payload=payload,
        )
        logger.debug("puppet_sync.enqueue_index work_item=%s", work_item_id)

    async def enqueue_delete(
        self,
        workspace_id: UUID,
        work_item_id: UUID,
    ) -> None:
        await self._outbox.enqueue(
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            operation="delete",
            payload={},
        )
        logger.debug("puppet_sync.enqueue_delete work_item=%s", work_item_id)
