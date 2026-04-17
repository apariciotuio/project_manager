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
    # Optional: populated when the emitter knows the work item owner.
    # NotificationSubscriber uses this to fan-out; if None the notification is skipped.
    # TODO(EP-08): update WorkItemService.transition_state to include owner_id once EP-06
    # lane restrictions are lifted.
    owner_id: UUID | None = None
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


# ---------------------------------------------------------------------------
# EP-08 — Notification trigger events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewRequestedEvent(Event):
    """Emitted when a review is requested on a work item.

    EP-06 is the canonical producer. If review_events.py exists at import time,
    that version takes precedence. This definition is here so the notification
    subscriber can register without depending on EP-06 being deployed first.
    TODO(EP-08/EP-06): consolidate into a single canonical definition.
    """

    work_item_id: UUID
    review_request_id: UUID
    requester_id: UUID
    reviewer_id: UUID
    workspace_id: UUID
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ReviewRespondedEvent(Event):
    """Emitted when a reviewer responds to a review request.

    TODO(EP-08/EP-06): consolidate with EP-06 canonical definition.
    """

    work_item_id: UUID
    review_request_id: UUID
    requester_id: UUID
    reviewer_id: UUID
    workspace_id: UUID
    decision: str  # "approved" | "changes_requested" | "rejected"
    response_content: str | None = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class CommentAddedEvent(Event):
    """Emitted when a comment is posted on a work item.

    Subscriber notifies the work item owner (fan-out to reviewers is deferred
    to a later iteration when reviewer list resolution is cheap).
    """

    work_item_id: UUID
    workspace_id: UUID
    comment_id: UUID
    author_id: UUID
    owner_id: UUID  # who owns the work item — pre-resolved by the emitter
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)
