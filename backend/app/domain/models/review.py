"""EP-06 — Review + Validation domain.

State machine for a ReviewRequest:
    pending -> closed      (when a response locks the request, e.g. approved)
    pending -> cancelled   (owner cancels)

Responses are append-only. Decision rules live in the service layer.

ValidationStatus no-regression table:
    pending  -> passed   OK
    pending  -> waived   OK
    pending  -> obsolete OK
    passed   -> passed   idempotent (OK)
    passed   -> *other   BLOCKED
    waived   -> *        BLOCKED
    obsolete -> *        BLOCKED
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


class ReviewInvariantError(Exception):
    """ReviewRequest constructed with invalid reviewer target."""


class ValidationTransitionError(Exception):
    """Forbidden ValidationStatus transition attempted."""


class WaiveRequiredRuleError(Exception):
    """waive() called on a required validation rule."""


_TERMINAL_VALIDATION_STATES = frozenset({
    ValidationState.PASSED, ValidationState.WAIVED, ValidationState.OBSOLETE
})


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

    def __post_init__(self) -> None:
        self._validate_reviewer_target()

    def _validate_reviewer_target(self) -> None:
        if self.reviewer_type is ReviewerType.USER:
            if self.reviewer_id is None or self.team_id is not None:
                raise ReviewInvariantError(
                    "reviewer_type=user requires reviewer_id set and team_id unset"
                )
        elif self.reviewer_type is ReviewerType.TEAM:
            if self.team_id is None or self.reviewer_id is not None:
                raise ReviewInvariantError(
                    "reviewer_type=team requires team_id set and reviewer_id unset"
                )

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

    @classmethod
    def create_for_team(
        cls,
        *,
        work_item_id: UUID,
        version_id: UUID,
        team_id: UUID,
        requested_by: UUID,
        validation_rule_id: str | None = None,
    ) -> ReviewRequest:
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            version_id=version_id,
            reviewer_type=ReviewerType.TEAM,
            reviewer_id=None,
            team_id=team_id,
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
    workspace_id: UUID | None = None
    description: str | None = None
    is_active: bool = True


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

    def transition_to(self, new_status: ValidationState) -> None:
        """Apply transition, enforcing no-regression invariant."""
        if self.status in _TERMINAL_VALIDATION_STATES:
            raise ValidationTransitionError(
                f"cannot transition from terminal state {self.status.value!r}"
            )
        self.status = new_status

    @classmethod
    def create_pending(cls, *, work_item_id: UUID, rule_id: str) -> ValidationStatus:
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            rule_id=rule_id,
            status=ValidationState.PENDING,
            passed_at=None,
            passed_by_review_request_id=None,
            waived_at=None,
            waived_by=None,
            waive_reason=None,
        )

    def mark_passed(self, *, by_review_request_id: UUID | None = None) -> None:
        """Mark passed. Idempotent if already PASSED. Raises on other terminal states."""
        if self.status is ValidationState.PASSED:
            return  # idempotent
        if self.status in _TERMINAL_VALIDATION_STATES:
            raise ValidationTransitionError(
                f"cannot mark passed from state {self.status.value!r}"
            )
        self.status = ValidationState.PASSED
        self.passed_at = datetime.now(UTC)
        self.passed_by_review_request_id = by_review_request_id

    def mark_waived(self, *, waived_by: UUID, waive_reason: str | None = None) -> None:
        if self.status in _TERMINAL_VALIDATION_STATES:
            raise ValidationTransitionError(
                f"cannot waive from state {self.status.value!r}"
            )
        self.status = ValidationState.WAIVED
        self.waived_at = datetime.now(UTC)
        self.waived_by = waived_by
        self.waive_reason = waive_reason
