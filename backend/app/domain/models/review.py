"""EP-06 — Review + Validation domain.

State machine for a ReviewRequest:
    pending -> closed      (when a response locks the request, e.g. approved)
    pending -> cancelled   (owner cancels)

Responses are append-only. Decision rules live in the service layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ReviewerType(StrEnum):
    USER = "user"
    TEAM = "team"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ValidationState(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    WAIVED = "waived"
    OBSOLETE = "obsolete"


class ReviewAlreadyClosedError(Exception):
    pass


class ContentRequiredError(Exception):
    pass


@dataclass
class ReviewRequest:
    id: UUID
    work_item_id: UUID
    version_id: UUID
    reviewer_type: ReviewerType
    reviewer_id: UUID | None
    team_id: UUID | None
    validation_rule_id: str | None
    status: ReviewStatus
    requested_by: UUID
    requested_at: datetime
    cancelled_at: datetime | None

    @classmethod
    def create_for_user(
        cls,
        *,
        work_item_id: UUID,
        version_id: UUID,
        reviewer_id: UUID,
        requested_by: UUID,
        validation_rule_id: str | None = None,
    ) -> ReviewRequest:
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            version_id=version_id,
            reviewer_type=ReviewerType.USER,
            reviewer_id=reviewer_id,
            team_id=None,
            validation_rule_id=validation_rule_id,
            status=ReviewStatus.PENDING,
            requested_by=requested_by,
            requested_at=datetime.now(UTC),
            cancelled_at=None,
        )

    def cancel(self) -> None:
        if self.status is not ReviewStatus.PENDING:
            raise ReviewAlreadyClosedError(
                f"cannot cancel review in status {self.status.value}"
            )
        self.status = ReviewStatus.CANCELLED
        self.cancelled_at = datetime.now(UTC)

    def close(self) -> None:
        if self.status is not ReviewStatus.PENDING:
            raise ReviewAlreadyClosedError(
                f"cannot close review in status {self.status.value}"
            )
        self.status = ReviewStatus.CLOSED


@dataclass(frozen=True)
class ReviewResponse:
    id: UUID
    review_request_id: UUID
    responder_id: UUID
    decision: ReviewDecision
    content: str | None
    responded_at: datetime

    @classmethod
    def create(
        cls,
        *,
        review_request_id: UUID,
        responder_id: UUID,
        decision: ReviewDecision,
        content: str | None = None,
    ) -> ReviewResponse:
        if decision is not ReviewDecision.APPROVED and not (content or "").strip():
            raise ContentRequiredError(
                "content is required when decision is not 'approved'"
            )
        return cls(
            id=uuid4(),
            review_request_id=review_request_id,
            responder_id=responder_id,
            decision=decision,
            content=content,
            responded_at=datetime.now(UTC),
        )


@dataclass(frozen=True)
class ValidationRequirement:
    rule_id: str
    label: str
    required: bool
    applies_to: tuple[str, ...]


@dataclass
class ValidationStatus:
    id: UUID
    work_item_id: UUID
    rule_id: str
    status: ValidationState
    passed_at: datetime | None
    passed_by_review_request_id: UUID | None
    waived_at: datetime | None
    waived_by: UUID | None
    waive_reason: str | None
