"""EP-10 — IValidationRuleTemplateRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.validation_rule_template import ValidationRuleTemplate


class IValidationRuleTemplateRepository(ABC):
    @abstractmethod
    async def create(self, template: ValidationRuleTemplate) -> ValidationRuleTemplate: ...

    @abstractmethod
    async def get(self, template_id: UUID) -> ValidationRuleTemplate | None: ...

    @abstractmethod
    async def list_for_workspace(self, workspace_id: UUID) -> list[ValidationRuleTemplate]: ...

    @abstractmethod
    async def list_matching(
        self,
        *,
        workspace_id: UUID,
        work_item_type: str | None,
    ) -> list[ValidationRuleTemplate]:
        """Return active templates that match workspace + type.

        Returns templates where:
        - workspace_id matches AND (work_item_type matches OR work_item_type is NULL)
        - plus global templates (workspace_id IS NULL) matching type
        Ordered by is_mandatory DESC, name ASC.
        """
        ...

    @abstractmethod
    async def save(self, template: ValidationRuleTemplate) -> ValidationRuleTemplate: ...

    @abstractmethod
    async def delete(self, template_id: UUID) -> None: ...
