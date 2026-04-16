"""Unit tests for EventBus."""
from __future__ import annotations

import pytest

from uuid import uuid4

from app.application.events.event_bus import Event, EventBus
from app.application.events.events import WorkItemCreatedEvent, WorkItemStateChangedEvent
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _created_event() -> WorkItemCreatedEvent:
    return WorkItemCreatedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        type=WorkItemType.BUG,
        creator_id=uuid4(),
        owner_id=uuid4(),
    )


def _state_changed_event() -> WorkItemStateChangedEvent:
    return WorkItemStateChangedEvent(
        work_item_id=uuid4(),
        workspace_id=uuid4(),
        from_state=WorkItemState.DRAFT,
        to_state=WorkItemState.IN_CLARIFICATION,
        actor_id=uuid4(),
        is_override=False,
        reason=None,
    )


# ---------------------------------------------------------------------------
# subscribe + emit round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_invokes_subscribed_handler(bus: EventBus) -> None:
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    evt = _created_event()
    bus.subscribe(WorkItemCreatedEvent, handler)
    await bus.emit(evt)

    assert len(received) == 1
    assert received[0] is evt


@pytest.mark.asyncio
async def test_emit_invokes_multiple_handlers(bus: EventBus) -> None:
    calls: list[str] = []

    async def h1(event: Event) -> None:
        calls.append("h1")

    async def h2(event: Event) -> None:
        calls.append("h2")

    bus.subscribe(WorkItemCreatedEvent, h1)
    bus.subscribe(WorkItemCreatedEvent, h2)
    await bus.emit(_created_event())

    assert calls == ["h1", "h2"]


@pytest.mark.asyncio
async def test_emit_no_handlers_is_noop(bus: EventBus) -> None:
    # Must not raise
    await bus.emit(_created_event())


# ---------------------------------------------------------------------------
# Handler exception isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_exception_does_not_prevent_other_handlers(bus: EventBus) -> None:
    reached: list[str] = []

    async def exploding_handler(event: Event) -> None:
        raise RuntimeError("boom")

    async def surviving_handler(event: Event) -> None:
        reached.append("survived")

    bus.subscribe(WorkItemCreatedEvent, exploding_handler)
    bus.subscribe(WorkItemCreatedEvent, surviving_handler)

    # emit() must not raise even when a handler blows up
    await bus.emit(_created_event())

    assert reached == ["survived"]


@pytest.mark.asyncio
async def test_emit_never_raises_on_handler_exception(bus: EventBus) -> None:
    async def bad_handler(event: Event) -> None:
        raise ValueError("bad")

    bus.subscribe(WorkItemCreatedEvent, bad_handler)
    # Should not propagate
    await bus.emit(_created_event())


# ---------------------------------------------------------------------------
# Event type isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_not_called_for_different_event_type(bus: EventBus) -> None:
    calls: list[str] = []

    async def created_handler(event: Event) -> None:
        calls.append("created")

    bus.subscribe(WorkItemCreatedEvent, created_handler)
    # Emit a different event type — handler must NOT fire
    await bus.emit(_state_changed_event())

    assert calls == []


@pytest.mark.asyncio
async def test_each_event_type_dispatches_independently(bus: EventBus) -> None:
    created_calls: list[Event] = []
    changed_calls: list[Event] = []

    async def on_created(event: Event) -> None:
        created_calls.append(event)

    async def on_changed(event: Event) -> None:
        changed_calls.append(event)

    bus.subscribe(WorkItemCreatedEvent, on_created)
    bus.subscribe(WorkItemStateChangedEvent, on_changed)

    await bus.emit(_created_event())
    await bus.emit(_state_changed_event())

    assert len(created_calls) == 1
    assert len(changed_calls) == 1
