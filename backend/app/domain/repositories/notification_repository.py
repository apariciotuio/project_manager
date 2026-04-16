"""EP-08 — INotificationRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.team import Notification


class INotificationRepository(ABC):
    @abstractmethod
    async def create(self, notification: Notification) -> Notification: ...

    @abstractmethod
    async def get(self, notification_id: UUID) -> Notification | None: ...

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Notification]: ...

    @abstractmethod
    async def mark_read(self, notification_id: UUID) -> None: ...

    @abstractmethod
    async def mark_actioned(self, notification_id: UUID) -> None: ...
