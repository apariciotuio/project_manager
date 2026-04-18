"""EP-08 — Extended notification service.

Adds mark_all_read, unread_count, and bulk_insert_idempotent on top of the
base NotificationService in team_service.py. Kept separate to avoid
modifying the EP-08 base that other parts of the app already import.

Controllers should inject ExtendedNotificationService via
get_extended_notification_service in dependencies.py.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.application.services.team_service import (
    NotificationService,
)
from app.domain.models.team import Notification
from app.domain.repositories.team_repository import INotificationRepository

logger = logging.getLogger(__name__)


class ExtendedNotificationService(NotificationService):
    """NotificationService + mark_all_read + unread_count + bulk_insert_idempotent."""

    def __init__(self, *, notification_repo: INotificationRepository) -> None:
        super().__init__(notification_repo=notification_repo)

    async def unread_count(self, *, user_id: UUID, workspace_id: UUID) -> int:
        """Return the number of unread notifications for the user."""
        return await self._notifications.unread_count(user_id, workspace_id)

    async def mark_all_read(self, *, user_id: UUID, workspace_id: UUID) -> int:
        """Bulk-mark all unread notifications for the user as read.

        Returns the number of updated rows.
        """
        updated = await self._notifications.mark_all_read(user_id, workspace_id)
        logger.info(
            "notification: mark_all_read user=%s workspace=%s updated=%d",
            user_id,
            workspace_id,
            updated,
        )
        return updated

    async def bulk_enqueue(
        self,
        *,
        notifications: list[Notification],
    ) -> list[Notification]:
        """Bulk-insert notifications idempotently.

        Used by Celery fan-out tasks so retries don't create duplicates.
        """
        return await self._notifications.bulk_insert_idempotent(notifications)
