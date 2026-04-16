"""EP-13 — Puppet outbox repository interface."""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class IPuppetOutboxRepository(Protocol):
    async def enqueue(
        self,
        workspace_id: UUID,
        work_item_id: UUID,
        operation: str,
        payload: dict[str, Any],
    ) -> None: ...

    async def claim_batch(self, limit: int = 50) -> list[dict[str, Any]]: ...

    async def mark_success(self, row_id: UUID) -> None: ...

    async def mark_failed(self, row_id: UUID, error: str) -> None: ...
