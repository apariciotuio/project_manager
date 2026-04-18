"""EP-08 — INotifier port.

Extension point for notification delivery adapters. For MVP the only
implementation is DatabaseNotifier (persist + rely on frontend polling).

Future adapters:
- EmailNotifier — sends transactional email via SES/SendGrid
- WebSocketPushNotifier — publishes to Redis pub/sub for SSE delivery

All adapters receive the persisted Notification domain object and are
responsible for their own error handling. Failures should be logged and
not propagated to callers (fire-and-forget delivery).
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

from app.domain.models.team import Notification


class INotifier(Protocol):
    """Protocol for notification delivery adapters."""

    @abstractmethod
    async def send(self, notification: Notification) -> None:
        """Deliver a notification to the recipient.

        Called after the notification has been persisted. Implementations
        should be idempotent — may be called more than once for the same
        notification on Celery retry.
        """
        ...


class DatabaseNotifier:
    """MVP notifier — notification is already persisted by the repository.

    This no-op implementation satisfies the INotifier protocol. The frontend
    polls GET /api/v1/notifications to receive new notifications. Future
    real-time delivery (SSE / WebSocket) is wired as an additional notifier.
    """

    async def send(self, notification: Notification) -> None:  # noqa: ARG002
        # Persistence is handled by NotificationRepositoryImpl.create() before
        # this is called. No additional transport required for MVP.
        pass
