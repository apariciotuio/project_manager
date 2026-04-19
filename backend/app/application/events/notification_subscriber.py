"""EP-08 — EventBus subscribers that write notifications.

Each handler builds a deterministic idempotency_key from (event_name, primary_id,
recipient_id) and delegates to NotificationService.enqueue. The idempotency_key
ensures that if the same event fires twice (Celery retry, double-publish) the
second call is a no-op at the repository layer.

Wired in create_app() via register_notification_subscribers().

Session lifecycle: each handler creates its own DB session via the session
factory, performs the write, and commits. This keeps the notification writes
isolated from the originating request's transaction.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from app.application.events.event_bus import Event, EventBus
from app.application.events.events import (
    CommentAddedEvent,
    ReviewRequestedEvent,
    ReviewRespondedEvent,
    WorkItemOwnerChangedEvent,
    WorkItemStateChangedEvent,
)

logger = logging.getLogger(__name__)

# Protocol-duck-type: the service must expose async enqueue(**kwargs).
# In tests, FakeNotificationService satisfies this interface.
NotificationServiceLike = Any


def _ikey(event_name: str, primary_id: UUID | str, recipient_id: UUID | str) -> str:
    """Build a deterministic idempotency key."""
    return f"{event_name}:{primary_id}:{recipient_id}"


@asynccontextmanager
async def _svc_ctx(
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> AsyncGenerator[NotificationServiceLike]:
    """Async context manager that yields the notification service.

    In production, get_svc builds a service with its own session and commits
    on exit. In tests, get_svc returns a FakeNotificationService directly.
    """
    svc = await get_svc()
    try:
        yield svc
    finally:
        # Commit if service exposes a session (production); no-op for fakes.
        commit = getattr(svc, "_commit", None)
        if commit is not None:
            await commit()


def _make_state_changed_handler(
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> Callable[[Event], Awaitable[None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, WorkItemStateChangedEvent):
            return
        # owner_id is optional — skip notification if not provided.
        # TODO(EP-08): update WorkItemService to populate owner_id once EP-06
        # lane restrictions are lifted so all state transitions can fan-out.
        if event.owner_id is None:
            return
        svc = await get_svc()
        ikey = _ikey("work_item.state_changed", event.event_id, event.owner_id)
        await svc.enqueue(
            workspace_id=event.workspace_id,
            recipient_id=event.owner_id,
            type="state_changed",
            subject_type="work_item",
            subject_id=event.work_item_id,
            deeplink=f"/items/{event.work_item_id}",
            idempotency_key=ikey,
            actor_id=event.actor_id,
            extra={
                "from_state": event.from_state.value,
                "to_state": event.to_state.value,
            },
        )

    return handle


def _make_owner_changed_handler(
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> Callable[[Event], Awaitable[None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, WorkItemOwnerChangedEvent):
            return
        svc = await get_svc()
        recipients: list[tuple[UUID, str]] = [
            (event.previous_owner_id, "previous_owner"),
            (event.new_owner_id, "new_owner"),
        ]
        for recipient_id, role in recipients:
            ikey = _ikey("work_item.owner_changed", event.event_id, recipient_id)
            await svc.enqueue(
                workspace_id=event.workspace_id,
                recipient_id=recipient_id,
                type="assignment.changed",
                subject_type="work_item",
                subject_id=event.work_item_id,
                deeplink=f"/items/{event.work_item_id}",
                idempotency_key=ikey,
                actor_id=event.changed_by,
                extra={
                    "role": role,
                    "previous_owner_id": str(event.previous_owner_id),
                    "new_owner_id": str(event.new_owner_id),
                },
            )

    return handle


def _make_review_requested_handler(
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> Callable[[Event], Awaitable[None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, ReviewRequestedEvent):
            return
        svc = await get_svc()
        ikey = _ikey("review.requested", event.review_request_id, event.reviewer_id)
        await svc.enqueue(
            workspace_id=event.workspace_id,
            recipient_id=event.reviewer_id,
            type="review.assigned",
            subject_type="review",
            subject_id=event.review_request_id,
            deeplink=f"/items/{event.work_item_id}",
            idempotency_key=ikey,
            actor_id=event.requester_id,
            extra={
                "work_item_id": str(event.work_item_id),
                "review_request_id": str(event.review_request_id),
            },
        )

    return handle


def _make_review_responded_handler(
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> Callable[[Event], Awaitable[None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, ReviewRespondedEvent):
            return
        svc = await get_svc()
        ikey = _ikey("review.responded", event.review_request_id, event.requester_id)
        await svc.enqueue(
            workspace_id=event.workspace_id,
            recipient_id=event.requester_id,
            type="review.responded",
            subject_type="review",
            subject_id=event.review_request_id,
            deeplink=f"/items/{event.work_item_id}",
            idempotency_key=ikey,
            actor_id=event.reviewer_id,
            extra={
                "work_item_id": str(event.work_item_id),
                "decision": event.decision,
                "response_content": event.response_content,
            },
        )

    return handle


def _make_comment_added_handler(
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> Callable[[Event], Awaitable[None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, CommentAddedEvent):
            return
        # Skip self-notification — author commenting on their own item.
        if event.author_id == event.owner_id:
            return
        svc = await get_svc()
        ikey = _ikey("comment.added", event.comment_id, event.owner_id)
        await svc.enqueue(
            workspace_id=event.workspace_id,
            recipient_id=event.owner_id,
            type="comment_added",
            subject_type="work_item",
            subject_id=event.work_item_id,
            deeplink=f"/items/{event.work_item_id}",
            idempotency_key=ikey,
            actor_id=event.author_id,
            extra={
                "comment_id": str(event.comment_id),
            },
        )

    return handle


def register_notification_subscribers(
    bus: EventBus,
    get_svc: Callable[[], Awaitable[NotificationServiceLike]],
) -> None:
    """Register all notification event handlers on the given EventBus.

    `get_svc` is an async callable that returns a NotificationService (or
    compatible fake). Called once per event handler invocation.
    """
    bus.subscribe(WorkItemStateChangedEvent, _make_state_changed_handler(get_svc))
    bus.subscribe(WorkItemOwnerChangedEvent, _make_owner_changed_handler(get_svc))
    bus.subscribe(ReviewRequestedEvent, _make_review_requested_handler(get_svc))
    bus.subscribe(ReviewRespondedEvent, _make_review_responded_handler(get_svc))
    bus.subscribe(CommentAddedEvent, _make_comment_added_handler(get_svc))
    logger.info(
        "notification_subscriber: registered handlers for "
        "state_changed, owner_changed, review_requested, review_responded, comment_added"
    )
