"""EP-07 — Repository interface for TimelineEvent."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.models.timeline_event import TimelineEvent


class ITimelineEventRepository(ABC):
    @abstractmethod
    async def insert(self, event: TimelineEvent) -> TimelineEvent: ...

    @abstractmethod
    async def list_for_work_item(
        self,
        work_item_id: UUID,
        *,
        before_occurred_at: datetime | None = None,
        before_id: UUID | None = None,
        limit: int = 50,
    ) -> list[TimelineEvent]: ...
