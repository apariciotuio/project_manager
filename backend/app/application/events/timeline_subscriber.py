"""EP-07 — EventBus subscribers that write timeline events.

Wired in `create_app()` after the EventBus is instantiated. Each handler is
fire-and-forget (errors are swallowed by the EventBus — see event_bus.py).

Handlers receive domain events from WorkItemService, ReviewService, etc. and
translate them into timeline_events rows via TimelineService.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.application.events.event_bus import Event, EventBus
from app.application.events.events import (
    WorkItemOwnerChangedEvent,
    WorkItemStateChangedEvent,
)
from app.application.services.timeline_service import TimelineService
from app.domain.models.timeline_event import TimelineActorType

logger = logging.getLogger(__name__)


def _make_state_changed_handler(
    get_svc: Callable[[], Coroutine[Any, Any, TimelineService]],
) -> Callable[[Event], Coroutine[Any, Any, None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, WorkItemStateChangedEvent):
            return
        svc = await get_svc()
        actor_type = TimelineActorType.HUMAN if event.actor_id else TimelineActorType.SYSTEM
        summary = (
            f"State changed from {event.from_state.value} to {event.to_state.value}"
        )
        if len(summary) > 255:
            summary = summary[:255]
        await svc.append(
            work_item_id=event.work_item_id,
            workspace_id=event.workspace_id,
            event_type="state_transition",
            actor_type=actor_type,
            actor_id=event.actor_id,
            summary=summary,
            payload={
                "from_state": event.from_state.value,
                "to_state": event.to_state.value,
                "is_override": event.is_override,
                "reason": event.reason,
            },
        )

    return handle


def _make_owner_changed_handler(
    get_svc: Callable[[], Coroutine[Any, Any, TimelineService]],
) -> Callable[[Event], Coroutine[Any, Any, None]]:
    async def handle(event: Event) -> None:
        if not isinstance(event, WorkItemOwnerChangedEvent):
            return
        svc = await get_svc()
        await svc.append(
            work_item_id=event.work_item_id,
            workspace_id=event.workspace_id,
            event_type="owner_changed",
            actor_type=TimelineActorType.HUMAN,
            actor_id=event.changed_by,
            summary="Owner changed",
            payload={
                "previous_owner_id": str(event.previous_owner_id),
                "new_owner_id": str(event.new_owner_id),
                "reason": event.reason,
            },
        )

    return handle


def register_timeline_subscribers(
    bus: EventBus,
    get_timeline_svc: Callable[[], Coroutine[Any, Any, TimelineService]],
) -> None:
    """Register all timeline event handlers on the given EventBus."""
    bus.subscribe(WorkItemStateChangedEvent, _make_state_changed_handler(get_timeline_svc))
    bus.subscribe(WorkItemOwnerChangedEvent, _make_owner_changed_handler(get_timeline_svc))
    logger.info("timeline_subscriber: registered handlers for state_changed, owner_changed")
