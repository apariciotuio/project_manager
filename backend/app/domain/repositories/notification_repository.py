"""EP-08 — INotificationRepository."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.team import Notification
from app.infrastructure.pagination import PaginationCursor, PaginationResult


class INotificationRepository(ABC):
    @abstractmethod
    async def create(self, notification: Notification) -> Notification:
        """Create a notification; no-op if `idempotency_key` already exists.

        Contract:
            - New key: persist `notification` unchanged and return it (same `id`).
            - Duplicate key: return the pre-existing row (its `id` differs from
              the supplied `notification.id`).

        Callers may use `returned.id == notification.id` to detect new rows.
        """
        ...

    @abstractmethod
    async def get(self, notification_id: UUID) -> Notification | None: ...

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Notification]: ...

    @abstractmethod
    async def list_inbox_cursor(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
    ) -> PaginationResult: ...

    @abstractmethod
    async def mark_read(self, notification_id: UUID) -> None: ...

    @abstractmethod
    async def mark_actioned(self, notification_id: UUID) -> None: ...
