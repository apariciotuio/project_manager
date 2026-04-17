"""EP-13 — IPuppetIngestRequestRepository interface."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.puppet_ingest_request import PuppetIngestRequest


class IPuppetIngestRequestRepository(Protocol):
    async def save(self, request: PuppetIngestRequest) -> None: ...

    async def get(self, request_id: UUID) -> PuppetIngestRequest | None: ...

    async def claim_queued_batch(self, workspace_id: UUID, limit: int) -> list[PuppetIngestRequest]: ...

    async def has_succeeded_for_work_item(self, work_item_id: UUID) -> bool: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[PuppetIngestRequest]: ...
