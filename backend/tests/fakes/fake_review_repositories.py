"""In-memory fakes for EP-06 Review + Validation repositories."""
from __future__ import annotations

from uuid import UUID

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


class FakeReviewRequestRepository(IReviewRequestRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, ReviewRequest] = {}

    async def get(self, request_id: UUID) -> ReviewRequest | None:
        return self._store.get(request_id)

    async def save(self, request: ReviewRequest) -> ReviewRequest:
        self._store[request.id] = request
        return request

    async def list_for_work_item(self, work_item_id: UUID) -> list[ReviewRequest]:
        return [r for r in self._store.values() if r.work_item_id == work_item_id]

    async def list_pending_for_reviewer(self, user_id: UUID) -> list[ReviewRequest]:
        return [
            r for r in self._store.values()
            if r.reviewer_id == user_id and r.status is ReviewStatus.PENDING
        ]


class FakeReviewResponseRepository(IReviewResponseRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, ReviewResponse] = {}

    async def create(self, response: ReviewResponse) -> ReviewResponse:
        self._store[response.id] = response
        return response

    async def get_for_request(self, request_id: UUID) -> ReviewResponse | None:
        return next(
            (r for r in self._store.values() if r.review_request_id == request_id), None
        )

    async def list_for_request(self, request_id: UUID) -> list[ReviewResponse]:
        return [r for r in self._store.values() if r.review_request_id == request_id]


class FakeValidationRequirementRepository(IValidationRequirementRepository):
    def __init__(self) -> None:
        self._store: dict[str, ValidationRequirement] = {}

    def seed(self, requirement: ValidationRequirement) -> None:
        self._store[requirement.rule_id] = requirement

    async def get(self, rule_id: str) -> ValidationRequirement | None:
        return self._store.get(rule_id)

    async def list_applicable(
        self,
        workspace_id: UUID,
        work_item_type: str,
        *,
        required_only: bool = False,
    ) -> list[ValidationRequirement]:
        results = []
        for rule in self._store.values():
            if not rule.is_active:
                continue
            if required_only and not rule.required:
                continue
            # applies_to empty = all types
            if not rule.applies_to or work_item_type in rule.applies_to:
                results.append(rule)
        return results

    async def save(self, requirement: ValidationRequirement) -> ValidationRequirement:
        self._store[requirement.rule_id] = requirement
        return requirement


class FakeValidationStatusRepository(IValidationStatusRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, ValidationStatus] = {}

    async def get(self, status_id: UUID) -> ValidationStatus | None:
        return self._store.get(status_id)

    async def get_by_work_item_and_rule(
        self, work_item_id: UUID, rule_id: str
    ) -> ValidationStatus | None:
        return next(
            (
                s for s in self._store.values()
                if s.work_item_id == work_item_id and s.rule_id == rule_id
            ),
            None,
        )

    async def save(self, status: ValidationStatus) -> ValidationStatus:
        self._store[status.id] = status
        return status

    async def list_for_work_item(self, work_item_id: UUID) -> list[ValidationStatus]:
        return [s for s in self._store.values() if s.work_item_id == work_item_id]

    async def list_blocking(self, work_item_id: UUID) -> list[ValidationStatus]:
        return [
            s for s in self._store.values()
            if s.work_item_id == work_item_id
            and s.status not in (ValidationState.PASSED, ValidationState.OBSOLETE)
        ]

    async def all_required_passed(self, work_item_id: UUID) -> bool:
        statuses = await self.list_for_work_item(work_item_id)
        return all(s.status is ValidationState.PASSED for s in statuses if s.rule_id)
