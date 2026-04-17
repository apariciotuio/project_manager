"""EP-06 — Domain events for Review and Validation lifecycle.

EP-08 imports these event classes directly to subscribe for notification fan-out.

Payload contracts (stable — changes require EP-08 coordination):

ReviewRequestedEvent:
  { work_item_id, review_request_id, requester_id, reviewer_id, workspace_id,
    reviewer_type, occurred_at }

ReviewRespondedEvent:
  { work_item_id, review_request_id, requester_id, reviewer_id, workspace_id,
    decision, response_content, occurred_at }

ReviewDismissedEvent (== cancelled):
  { work_item_id, review_request_id, requester_id, reviewer_id, workspace_id, occurred_at }

ValidationStatusChangedEvent:
  { work_item_id, rule_id, workspace_id, new_status, occurred_at }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.events.event_bus import Event


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ReviewRequestedEvent(Event):
    """Emitted when a review request is created."""

    work_item_id: UUID
    review_request_id: UUID
    requester_id: UUID
    reviewer_id: UUID | None        # None when reviewer_type=team
    workspace_id: UUID
    reviewer_type: str              # "user" | "team"
    team_id: UUID | None = None     # set when reviewer_type=team
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ReviewRespondedEvent(Event):
    """Emitted when a reviewer submits a response (approved/rejected/changes_requested)."""

    work_item_id: UUID
    review_request_id: UUID
    requester_id: UUID
    reviewer_id: UUID | None
    workspace_id: UUID
    decision: str                   # "approved" | "rejected" | "changes_requested"
    response_content: str | None = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ReviewDismissedEvent(Event):
    """Emitted when a review request is cancelled (dismissed) by the owner."""

    work_item_id: UUID
    review_request_id: UUID
    requester_id: UUID
    reviewer_id: UUID | None
    workspace_id: UUID
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ValidationStatusChangedEvent(Event):
    """Emitted when a validation status flips (especially pending->passed for all_mandatory_satisfied)."""

    work_item_id: UUID
    rule_id: str
    workspace_id: UUID
    new_status: str                 # "pending" | "passed" | "waived" | "obsolete"
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)
