"""EP-13 — PuppetIngestService.

Orchestrates creation and dispatch of puppet_ingest_requests rows.
Keeps business logic out of the Celery task and controllers.

Idempotency:
  If a succeeded row already exists for the same work_item_id, mark_skipped is
  called immediately — no HTTP call to Puppet.

Retry policy (enforced by caller):
  - attempts < 3: re-queue on failure (status back to 'queued')
  - attempts >= 3: leave as 'failed' for manual retry
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.domain.models.puppet_ingest_request import PuppetIngestRequest
from app.domain.ports.puppet import PuppetClient
from app.infrastructure.persistence.puppet_ingest_request_repository_impl import (
    PuppetIngestRequestRepositoryImpl,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


class PuppetIngestService:
    def __init__(
        self,
        ingest_repo: PuppetIngestRequestRepositoryImpl,
        puppet_client: PuppetClient,
    ) -> None:
        self._repo = ingest_repo
        self._puppet = puppet_client

    async def enqueue(
        self,
        workspace_id: UUID,
        work_item_id: UUID,
        source_kind: str = "outbox",
        payload: dict[str, Any] | None = None,
    ) -> PuppetIngestRequest:
        """Create a new queued ingest request row."""
        request = PuppetIngestRequest.create(
            workspace_id=workspace_id,
            source_kind=source_kind,
            work_item_id=work_item_id,
            payload=payload or {},
        )
        await self._repo.save(request)
        logger.debug(
            "puppet_ingest.enqueue workspace=%s work_item=%s source=%s",
            workspace_id,
            work_item_id,
            source_kind,
        )
        return request

    async def dispatch_pending(self, workspace_id: UUID, limit: int = 50) -> int:
        """Claim queued rows and call Puppet for each.

        Returns number of rows processed (success + failed + skipped).
        """
        rows = await self._repo.claim_queued_batch(workspace_id, limit)
        if not rows:
            return 0

        processed = 0
        for row in rows:
            try:
                # Idempotency: skip if work_item already succeeded via a previous row
                if row.work_item_id is not None:
                    already_done = await self._repo.has_succeeded_for_work_item(row.work_item_id)
                    if already_done:
                        row.mark_skipped("already succeeded via previous ingest request")
                        await self._repo.save(row)
                        processed += 1
                        logger.debug(
                            "puppet_ingest.skipped work_item=%s (already succeeded)",
                            row.work_item_id,
                        )
                        continue

                content: str = row.payload.get("content", "")
                tags: list[str] = row.payload.get("tags", [])
                doc_id = str(row.work_item_id or row.id)

                result = await self._puppet.index_document(doc_id, content, tags)
                puppet_doc_id: str = result.get("doc_id", doc_id)
                row.mark_succeeded(puppet_doc_id)
                await self._repo.save(row)
                logger.info(
                    "puppet_ingest.succeeded id=%s work_item=%s puppet_doc_id=%s",
                    row.id,
                    row.work_item_id,
                    puppet_doc_id,
                )
            except Exception as exc:  # noqa: BLE001
                error_msg = str(exc)[:500]
                row.mark_failed(error_msg)
                # Re-queue if under max attempts
                if row.attempts < _MAX_ATTEMPTS:
                    row.reset_for_retry()
                    logger.warning(
                        "puppet_ingest.retry id=%s attempt=%d/%d error=%s",
                        row.id,
                        row.attempts,
                        _MAX_ATTEMPTS,
                        error_msg,
                    )
                else:
                    logger.error(
                        "puppet_ingest.dead_letter id=%s attempts=%d error=%s",
                        row.id,
                        row.attempts,
                        error_msg,
                    )
                await self._repo.save(row)

            processed += 1

        return processed
