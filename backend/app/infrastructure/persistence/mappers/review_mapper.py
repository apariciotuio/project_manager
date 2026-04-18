"""Mappers for ReviewRequest, ReviewResponse, ValidationRequirement, ValidationStatus — EP-06."""

from __future__ import annotations

from app.domain.models.review import (  # noqa: I001
    ReviewDecision,
    ReviewerType,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
    ValidationRequirement,
    ValidationState,
    ValidationStatus,
)
from app.infrastructure.persistence.models.orm import (
    ReviewRequestORM,
    ReviewResponseORM,
    ValidationRequirementORM,
    ValidationStatusORM,
)


def review_request_to_domain(row: ReviewRequestORM) -> ReviewRequest:
    return ReviewRequest(
        id=row.id,
        work_item_id=row.work_item_id,
        version_id=row.version_id,
        reviewer_type=ReviewerType(row.reviewer_type),
        reviewer_id=row.reviewer_id,
        team_id=row.team_id,
        validation_rule_id=row.validation_rule_id,
        status=ReviewStatus(row.status),
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        cancelled_at=row.cancelled_at,
    )


def review_request_to_orm(entity: ReviewRequest) -> ReviewRequestORM:
    row = ReviewRequestORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.version_id = entity.version_id
    row.reviewer_type = entity.reviewer_type.value
    row.reviewer_id = entity.reviewer_id
    row.team_id = entity.team_id
    row.validation_rule_id = entity.validation_rule_id
    row.status = entity.status.value
    row.requested_by = entity.requested_by
    row.requested_at = entity.requested_at
    row.cancelled_at = entity.cancelled_at
    return row


def review_response_to_domain(row: ReviewResponseORM) -> ReviewResponse:
    return ReviewResponse(
        id=row.id,
        review_request_id=row.review_request_id,
        responder_id=row.responder_id,
        decision=ReviewDecision(row.decision),
        content=row.content,
        responded_at=row.responded_at,
    )


def review_response_to_orm(entity: ReviewResponse) -> ReviewResponseORM:
    row = ReviewResponseORM()
    row.id = entity.id
    row.review_request_id = entity.review_request_id
    row.responder_id = entity.responder_id
    row.decision = entity.decision.value
    row.content = entity.content
    row.responded_at = entity.responded_at
    return row


def validation_status_to_domain(row: ValidationStatusORM) -> ValidationStatus:
    return ValidationStatus(
        id=row.id,
        work_item_id=row.work_item_id,
        rule_id=row.rule_id,
        status=ValidationState(row.status),
        passed_at=row.passed_at,
        passed_by_review_request_id=row.passed_by_review_request_id,
        waived_at=row.waived_at,
        waived_by=row.waived_by,
        waive_reason=row.waive_reason,
    )


def validation_requirement_to_domain(row: ValidationRequirementORM) -> ValidationRequirement:
    return ValidationRequirement(
        rule_id=row.rule_id,
        label=row.label,
        required=row.required,
        applies_to=tuple(row.applies_to.split(",") if row.applies_to else []),
        workspace_id=row.workspace_id,
        description=row.description,
        is_active=row.is_active,
    )


def validation_status_to_orm(entity: ValidationStatus) -> ValidationStatusORM:
    row = ValidationStatusORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.rule_id = entity.rule_id
    row.status = entity.status.value
    row.passed_at = entity.passed_at
    row.passed_by_review_request_id = entity.passed_by_review_request_id
    row.waived_at = entity.waived_at
    row.waived_by = entity.waived_by
    row.waive_reason = entity.waive_reason
    return row
