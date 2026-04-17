"""EP-08 — Unit tests for NotificationSubscriber.

RED phase: these tests verify that event handlers build the correct idempotency
keys, call NotificationService.enqueue with the right parameters, and that
duplicate events do NOT call enqueue a second time.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.events.event_bus import EventBus
from app.application.events.events import (
    CommentAddedEvent,
    ReviewRequestedEvent,
    ReviewRespondedEvent,
    WorkItemOwnerChangedEvent,
    WorkItemStateChangedEvent,
)
from app.domain.value_objects.work_item_state import WorkItemState


# ---------------------------------------------------------------------------
# Fake NotificationService
# ---------------------------------------------------------------------------


class FakeNotificationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        # Track idempotency_keys to simulate dedup
        self._seen: set[str] = set()

    async def enqueue(self, *, idempotency_key: str, **kwargs: Any) -> object:
        if idempotency_key in self._seen:
            return object()  # already exists — no-op
        self._seen.add(idempotency_key)
        self.calls.append({"idempotency_key": idempotency_key, **kwargs})
        return object()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> FakeNotificationService:
    return FakeNotificationService()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def _register(bus: EventBus, svc: FakeNotificationService) -> None:
    from app.application.events.notification_subscriber import (
        register_notification_subscribers,
    )

    async def _get_svc() -> FakeNotificationService:
        return svc

    register_notification_subscribers(bus, _get_svc)


# ---------------------------------------------------------------------------
# WorkItemStateChangedEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_changed_notifies_owner(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    owner_id = uuid4()
    evt = WorkItemStateChangedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        from_state=WorkItemState.DRAFT,
        to_state=WorkItemState.IN_CLARIFICATION,
        actor_id=uuid4(),
        is_override=False,
        reason=None,
        owner_id=owner_id,
    )
    await bus.emit(evt)
    assert any(c["recipient_id"] == owner_id for c in svc.calls)


@pytest.mark.asyncio
async def test_state_changed_idempotent_on_double_emit(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    owner_id = uuid4()
    evt = WorkItemStateChangedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        from_state=WorkItemState.DRAFT,
        to_state=WorkItemState.IN_CLARIFICATION,
        actor_id=uuid4(),
        is_override=False,
        reason=None,
        owner_id=owner_id,
    )
    await bus.emit(evt)
    await bus.emit(evt)
    owner_calls = [c for c in svc.calls if c["recipient_id"] == owner_id]
    assert len(owner_calls) == 1


# ---------------------------------------------------------------------------
# WorkItemOwnerChangedEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_changed_notifies_previous_and_new(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    previous = uuid4()
    new = uuid4()
    evt = WorkItemOwnerChangedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        previous_owner_id=previous,
        new_owner_id=new,
        changed_by=uuid4(),
        reason=None,
    )
    await bus.emit(evt)
    recipients = {c["recipient_id"] for c in svc.calls}
    assert previous in recipients
    assert new in recipients


@pytest.mark.asyncio
async def test_owner_changed_idempotent(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    evt = WorkItemOwnerChangedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        previous_owner_id=uuid4(),
        new_owner_id=uuid4(),
        changed_by=uuid4(),
        reason=None,
    )
    await bus.emit(evt)
    count_before = len(svc.calls)
    await bus.emit(evt)
    assert len(svc.calls) == count_before  # no new calls — all keys already seen


# ---------------------------------------------------------------------------
# ReviewRequestedEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_requested_notifies_reviewer(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    reviewer_id = uuid4()
    evt = ReviewRequestedEvent(
        work_item_id=uuid4(),
        review_request_id=uuid4(),
        requester_id=uuid4(),
        reviewer_id=reviewer_id,
        workspace_id=uuid4(),
    )
    await bus.emit(evt)
    assert any(c["recipient_id"] == reviewer_id for c in svc.calls)


@pytest.mark.asyncio
async def test_review_requested_idempotent(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    evt = ReviewRequestedEvent(
        work_item_id=uuid4(),
        review_request_id=uuid4(),
        requester_id=uuid4(),
        reviewer_id=uuid4(),
        workspace_id=uuid4(),
    )
    await bus.emit(evt)
    await bus.emit(evt)
    assert len(svc.calls) == 1


# ---------------------------------------------------------------------------
# ReviewRespondedEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_responded_notifies_requester(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    requester_id = uuid4()
    evt = ReviewRespondedEvent(
        work_item_id=uuid4(),
        review_request_id=uuid4(),
        requester_id=requester_id,
        reviewer_id=uuid4(),
        workspace_id=uuid4(),
        decision="approved",
    )
    await bus.emit(evt)
    assert any(c["recipient_id"] == requester_id for c in svc.calls)


# ---------------------------------------------------------------------------
# CommentAddedEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comment_added_notifies_owner(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    _register(bus, svc)
    owner_id = uuid4()
    evt = CommentAddedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        comment_id=uuid4(),
        author_id=uuid4(),
        owner_id=owner_id,
    )
    await bus.emit(evt)
    assert any(c["recipient_id"] == owner_id for c in svc.calls)


@pytest.mark.asyncio
async def test_comment_added_skips_self_notification(
    bus: EventBus, svc: FakeNotificationService
) -> None:
    """Author commenting on their own item should not notify themselves."""
    _register(bus, svc)
    user_id = uuid4()
    evt = CommentAddedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        comment_id=uuid4(),
        author_id=user_id,
        owner_id=user_id,  # same person
    )
    await bus.emit(evt)
    assert len(svc.calls) == 0
