"""EP-04 — IValidatorRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.validator import Validator


class IValidatorRepository(ABC):
    @abstractmethod
    async def get(self, validator_id: UUID) -> Validator | None: ...

    @abstractmethod
    async def get_by_work_item(self, work_item_id: UUID) -> list[Validator]: ...

    @abstractmethod
    async def assign(self, validator: Validator) -> Validator: ...

    @abstractmethod
    async def save(self, validator: Validator) -> Validator: ...
