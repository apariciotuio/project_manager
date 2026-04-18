"""IGapFindingRepository — domain-layer interface for gap finding persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.models.gap_finding import StoredGapFinding


class IGapFindingRepository(ABC):
    @abstractmethod
    async def insert_many(self, findings: list[StoredGapFinding]) -> list[StoredGapFinding]:
        """Bulk-insert findings. Returns persisted entities with server-assigned ids/timestamps."""

    @abstractmethod
    async def get_active_for_work_item(
        self,
        work_item_id: UUID,
        source: str | None = None,
    ) -> list[StoredGapFinding]:
        """Return non-invalidated findings for a work item.

        When ``source`` is provided, filters to that source only.
        """

    @abstractmethod
    async def invalidate_for_work_item(
        self,
        work_item_id: UUID,
        now: datetime,
        source: str | None = None,
    ) -> int:
        """Single-query bulk invalidation. Sets invalidated_at on active findings.

        When ``source`` is None, invalidates ALL active findings for the work item.
        When ``source`` is provided, only findings matching that source are invalidated.
        Returns count of rows updated.
        """
