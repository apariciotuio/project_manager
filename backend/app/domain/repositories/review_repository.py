"""EP-06 — Repository interfaces for Review + Validation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.review import (
    ReviewRequest,
    ReviewResponse,
    ValidationRequirement,
    ValidationStatus,
)


class IReviewRequestRepository(ABC):
    @abstractmethod
    async def get(self, request_id: UUID) -> ReviewRequest | None: ...

    @abstractmethod
    async def save(self, request: ReviewRequest) -> ReviewRequest: ...

    @abstractmethod
    async def list_for_work_item(self, work_item_id: UUID) -> list[ReviewRequest]: ...

    @abstractmethod
    async def list_pending_for_reviewer(self, user_id: UUID) -> list[ReviewRequest]: ...


class IReviewResponseRepository(ABC):
    @abstractmethod
    async def create(self, response: ReviewResponse) -> ReviewResponse: ...

    @abstractmethod
    async def get_for_request(self, request_id: UUID) -> ReviewResponse | None: ...

    @abstractmethod
    async def list_for_request(self, request_id: UUID) -> list[ReviewResponse]: ...


class IValidationRequirementRepository(ABC):
    @abstractmethod
    async def get(self, rule_id: str) -> ValidationRequirement | None: ...

    @abstractmethod
    async def list_applicable(
        self,
        workspace_id: UUID,
        work_item_type: str,
        *,
        required_only: bool = False,
    ) -> list[ValidationRequirement]: ...

    @abstractmethod
    async def save(self, requirement: ValidationRequirement) -> ValidationRequirement: ...


class IValidationStatusRepository(ABC):
    @abstractmethod
    async def get(self, status_id: UUID) -> ValidationStatus | None: ...

    @abstractmethod
    async def get_by_work_item_and_rule(
        self, work_item_id: UUID, rule_id: str
    ) -> ValidationStatus | None: ...

    @abstractmethod
    async def save(self, status: ValidationStatus) -> ValidationStatus: ...

    @abstractmethod
    async def list_for_work_item(self, work_item_id: UUID) -> list[ValidationStatus]: ...

    @abstractmethod
    async def list_blocking(self, work_item_id: UUID) -> list[ValidationStatus]:
        """Return all non-passed, non-obsolete statuses for required rules (gate hot path)."""
        ...

    @abstractmethod
    async def all_required_passed(self, work_item_id: UUID) -> bool: ...
