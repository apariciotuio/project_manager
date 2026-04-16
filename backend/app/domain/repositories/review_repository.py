"""EP-06 — Repository interfaces for Review + Validation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.review import (
    ReviewRequest,
    ReviewResponse,
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
    async def list_for_request(self, request_id: UUID) -> list[ReviewResponse]: ...


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
    async def all_required_passed(self, work_item_id: UUID) -> bool: ...
