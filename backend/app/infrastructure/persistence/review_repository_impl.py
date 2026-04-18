"""EP-06 — SQLAlchemy implementations for Review + Validation repos."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.review import (
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
    ValidationRequirement,
    ValidationState,
    ValidationStatus,
)
from app.domain.repositories.review_repository import (
    IReviewRequestRepository,
    IReviewResponseRepository,
    IValidationRequirementRepository,
    IValidationStatusRepository,
)
from app.infrastructure.persistence.mappers.review_mapper import (
    review_request_to_domain,
    review_request_to_orm,
    review_response_to_domain,
    review_response_to_orm,
    validation_requirement_to_domain,
    validation_status_to_domain,
    validation_status_to_orm,
)
from app.infrastructure.persistence.models.orm import (
    ReviewRequestORM,
    ReviewResponseORM,
    ValidationRequirementORM,
    ValidationStatusORM,
)


class ReviewRequestRepositoryImpl(IReviewRequestRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, request_id: UUID) -> ReviewRequest | None:
        row = await self._session.get(ReviewRequestORM, request_id)
        return review_request_to_domain(row) if row else None

    async def save(self, request: ReviewRequest) -> ReviewRequest:
        existing = await self._session.get(ReviewRequestORM, request.id)
        if existing is None:
            self._session.add(review_request_to_orm(request))
        else:
            existing.status = request.status.value
            existing.cancelled_at = request.cancelled_at
        await self._session.flush()
        return request

    async def list_for_work_item(self, work_item_id: UUID) -> list[ReviewRequest]:
        stmt = (
            select(ReviewRequestORM)
            .where(ReviewRequestORM.work_item_id == work_item_id)
            .order_by(ReviewRequestORM.requested_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [review_request_to_domain(r) for r in rows]

    async def list_pending_for_reviewer(self, user_id: UUID) -> list[ReviewRequest]:
        stmt = (
            select(ReviewRequestORM)
            .where(
                and_(
                    ReviewRequestORM.reviewer_id == user_id,
                    ReviewRequestORM.status == ReviewStatus.PENDING.value,
                )
            )
            .order_by(ReviewRequestORM.requested_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [review_request_to_domain(r) for r in rows]

    async def has_open_reviews_for_team(self, team_id: UUID) -> bool:
        stmt = select(
            exists().where(
                and_(
                    ReviewRequestORM.team_id == team_id,
                    ReviewRequestORM.status == ReviewStatus.PENDING.value,
                )
            )
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar())


class ReviewResponseRepositoryImpl(IReviewResponseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, response: ReviewResponse) -> ReviewResponse:
        self._session.add(review_response_to_orm(response))
        await self._session.flush()
        return response

    async def get_for_request(self, request_id: UUID) -> ReviewResponse | None:
        stmt = select(ReviewResponseORM).where(ReviewResponseORM.review_request_id == request_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return review_response_to_domain(row) if row else None

    async def list_for_request(self, request_id: UUID) -> list[ReviewResponse]:
        stmt = (
            select(ReviewResponseORM)
            .where(ReviewResponseORM.review_request_id == request_id)
            .order_by(ReviewResponseORM.responded_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [review_response_to_domain(r) for r in rows]


class ValidationRequirementRepositoryImpl(IValidationRequirementRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, rule_id: str) -> ValidationRequirement | None:
        row = await self._session.get(ValidationRequirementORM, rule_id)
        return validation_requirement_to_domain(row) if row else None

    async def list_applicable(
        self,
        workspace_id: UUID,
        work_item_type: str,
        *,
        required_only: bool = False,
    ) -> list[ValidationRequirement]:
        """Return active rules applicable to this workspace + work_item_type.

        Rules with workspace_id=NULL are global defaults visible to all workspaces.
        Workspace-scoped rules (workspace_id=workspace_id) extend or override globals.
        applies_to='' (empty) means the rule applies to all types.
        """
        stmt = select(ValidationRequirementORM).where(
            and_(
                ValidationRequirementORM.is_active.is_(True),
                or_(
                    ValidationRequirementORM.workspace_id.is_(None),
                    ValidationRequirementORM.workspace_id == workspace_id,
                ),
            )
        )
        if required_only:
            stmt = stmt.where(ValidationRequirementORM.required.is_(True))
        rows = (await self._session.execute(stmt)).scalars().all()
        # Filter by applies_to: empty string / empty list = applies to all types
        result = []
        for row in rows:
            if not row.applies_to or work_item_type in row.applies_to.split(","):
                result.append(validation_requirement_to_domain(row))
        return result

    async def save(self, requirement: ValidationRequirement) -> ValidationRequirement:
        row = await self._session.get(ValidationRequirementORM, requirement.rule_id)
        if row is None:
            new_row = ValidationRequirementORM()
            new_row.rule_id = requirement.rule_id
            new_row.label = requirement.label
            new_row.required = requirement.required
            new_row.applies_to = ",".join(requirement.applies_to)
            new_row.workspace_id = requirement.workspace_id
            new_row.description = requirement.description
            new_row.is_active = requirement.is_active
            self._session.add(new_row)
        else:
            row.label = requirement.label
            row.required = requirement.required
            row.applies_to = ",".join(requirement.applies_to)
            row.description = requirement.description
            row.is_active = requirement.is_active
        await self._session.flush()
        return requirement


class ValidationStatusRepositoryImpl(IValidationStatusRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, status_id: UUID) -> ValidationStatus | None:
        row = await self._session.get(ValidationStatusORM, status_id)
        return validation_status_to_domain(row) if row else None

    async def get_by_work_item_and_rule(
        self, work_item_id: UUID, rule_id: str
    ) -> ValidationStatus | None:
        stmt = select(ValidationStatusORM).where(
            and_(
                ValidationStatusORM.work_item_id == work_item_id,
                ValidationStatusORM.rule_id == rule_id,
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return validation_status_to_domain(row) if row else None

    async def save(self, status: ValidationStatus) -> ValidationStatus:
        existing = await self._session.get(ValidationStatusORM, status.id)
        if existing is None:
            self._session.add(validation_status_to_orm(status))
        else:
            existing.status = status.status.value
            existing.passed_at = status.passed_at
            existing.passed_by_review_request_id = status.passed_by_review_request_id
            existing.waived_at = status.waived_at
            existing.waived_by = status.waived_by
            existing.waive_reason = status.waive_reason
        await self._session.flush()
        return status

    async def list_for_work_item(self, work_item_id: UUID) -> list[ValidationStatus]:
        stmt = select(ValidationStatusORM).where(ValidationStatusORM.work_item_id == work_item_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [validation_status_to_domain(r) for r in rows]

    async def list_blocking(self, work_item_id: UUID) -> list[ValidationStatus]:
        """Return non-passed, non-obsolete statuses — gate hot path."""
        stmt = select(ValidationStatusORM).where(
            and_(
                ValidationStatusORM.work_item_id == work_item_id,
                ValidationStatusORM.status.notin_(
                    [ValidationState.PASSED.value, ValidationState.OBSOLETE.value]
                ),
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [validation_status_to_domain(r) for r in rows]

    async def all_required_passed(self, work_item_id: UUID) -> bool:
        """Returns True if every required ValidationRequirement has a PASSED ValidationStatus."""
        req_stmt = select(ValidationRequirementORM.rule_id).where(
            ValidationRequirementORM.required.is_(True)
        )
        required_rule_ids = set((await self._session.execute(req_stmt)).scalars().all())
        if not required_rule_ids:
            return True

        passed_stmt = select(ValidationStatusORM.rule_id).where(
            and_(
                ValidationStatusORM.work_item_id == work_item_id,
                ValidationStatusORM.rule_id.in_(required_rule_ids),
                ValidationStatusORM.status == ValidationState.PASSED.value,
            )
        )
        passed_rule_ids = set((await self._session.execute(passed_stmt)).scalars().all())
        return required_rule_ids <= passed_rule_ids
