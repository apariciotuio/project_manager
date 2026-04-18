"""Repository interface for ValidationRule."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.validation_rule import ValidationRule


class IValidationRuleRepository(ABC):
    @abstractmethod
    async def create(self, rule: ValidationRule) -> ValidationRule: ...

    @abstractmethod
    async def get_by_id(self, rule_id: UUID, workspace_id: UUID) -> ValidationRule | None: ...

    @abstractmethod
    async def list_for_workspace(
        self,
        workspace_id: UUID,
        *,
        project_id: UUID | None = None,
        work_item_type: str | None = None,
        active_only: bool = True,
    ) -> list[ValidationRule]: ...

    @abstractmethod
    async def save(self, rule: ValidationRule) -> ValidationRule: ...

    @abstractmethod
    async def delete(self, rule_id: UUID, workspace_id: UUID) -> None: ...

    @abstractmethod
    async def has_history(self, rule_id: UUID) -> bool:
        """Return True if any audit events reference this rule (hard-delete guard)."""
        ...
