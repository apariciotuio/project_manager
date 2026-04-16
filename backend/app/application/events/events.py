"""Domain events emitted by WorkItemService.

All events are frozen dataclasses subclassing Event. Each carries event_id and
occurred_at for idempotency and ordering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.events.event_bus import Event
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class WorkItemCreatedEvent(Event):
    work_item_id: UUID
    workspace_id: UUID
    type: WorkItemType
    creator_id: UUID
    owner_id: UUID
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkItemStateChangedEvent(Event):
    work_item_id: UUID
    workspace_id: UUID
    from_state: WorkItemState
    to_state: WorkItemState
    actor_id: UUID | None  # None when actor is the system
    is_override: bool
    reason: str | None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkItemReadyOverrideEvent(Event):
    work_item_id: UUID
    workspace_id: UUID
    actor_id: UUID
    justification: str
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkItemRevertedFromReadyEvent(Event):
    """Emitted when a content change on a READY item auto-reverts it to IN_CLARIFICATION."""

    work_item_id: UUID
    workspace_id: UUID
    actor_id: UUID | None  # None = system-triggered
    reason: str | None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkItemOwnerChangedEvent(Event):
    work_item_id: UUID
    workspace_id: UUID
    previous_owner_id: UUID
    new_owner_id: UUID
    changed_by: UUID
    reason: str | None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkItemChangesRequestedEvent(Event):
    """Emitted when reviewer triggers in_review → changes_requested."""

    work_item_id: UUID
    workspace_id: UUID
    reviewer_id: UUID
    notes: str | None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkItemContentChangedAfterReadyEvent(Event):
    """Fires BEFORE the revert event when content fields change on a READY item."""

    work_item_id: UUID
    workspace_id: UUID
    actor_id: UUID
    changed_fields: tuple[str, ...]
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class WorkspaceMemberSuspendedWithActiveItemsEvent(Event):
    """Emitted when a workspace member is suspended and has active work items.

    EP-10 wires the producer. Defined here so EP-01 handlers can subscribe.
    """

    workspace_id: UUID
    user_id: UUID
    active_item_count: int
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)
