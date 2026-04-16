"""EP-08 — NotificationService."""
from __future__ import annotations

from uuid import UUID

from app.domain.models.team import Notification
from app.domain.repositories.notification_repository import INotificationRepository


class NotificationService:
    def __init__(self, *, notification_repo: INotificationRepository) -> None:
        self._notifications = notification_repo

    async def enqueue(self, notification: Notification) -> Notification:
        return await self._notifications.create(notification)

    async def list_inbox(
        self, user_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        return await self._notifications.list_for_user(
            user_id, limit=limit, offset=offset
        )

    async def mark_read(self, notification_id: UUID) -> None:
        await self._notifications.mark_read(notification_id)

    async def mark_actioned(self, notification_id: UUID) -> None:
        await self._notifications.mark_actioned(notification_id)
