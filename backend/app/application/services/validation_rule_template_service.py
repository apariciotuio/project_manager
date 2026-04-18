"""EP-10 — ValidationRuleTemplateService."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.validation_rule_template import ValidationRuleTemplate
from app.domain.repositories.validation_rule_template_repository import (
    IValidationRuleTemplateRepository,
)


class ValidationRuleTemplateNotFoundError(LookupError):
    pass


class ValidationRuleTemplateService:
    def __init__(self, *, repo: IValidationRuleTemplateRepository) -> None:
        self._repo = repo

    async def create(
        self,
        *,
        name: str,
        requirement_type: str,
        is_mandatory: bool,
        workspace_id: UUID | None = None,
        work_item_type: str | None = None,
        default_dimension: str | None = None,
        default_description: str | None = None,
    ) -> ValidationRuleTemplate:
        template = ValidationRuleTemplate.create(
            name=name,
            requirement_type=requirement_type,
            is_mandatory=is_mandatory,
            workspace_id=workspace_id,
            work_item_type=work_item_type,
            default_dimension=default_dimension,
            default_description=default_description,
        )
        return await self._repo.create(template)

    async def get(
        self, template_id: UUID, *, workspace_id: UUID | None = None
    ) -> ValidationRuleTemplate:
        template = await self._repo.get(template_id)
        if template is None:
            raise ValidationRuleTemplateNotFoundError(
                f"validation rule template {template_id} not found"
            )
        # Workspace scoping: workspace templates must belong to caller's workspace;
        # global templates (workspace_id=None) are accessible to everyone.
        if (
            workspace_id is not None
            and template.workspace_id is not None
            and template.workspace_id != workspace_id
        ):
            raise ValidationRuleTemplateNotFoundError(
                f"validation rule template {template_id} not found"
            )
        return template

    async def list_for_workspace(self, workspace_id: UUID) -> list[ValidationRuleTemplate]:
        return await self._repo.list_for_workspace(workspace_id)

    async def update(
        self,
        template_id: UUID,
        *,
        workspace_id: UUID | None = None,
        name: str | None = None,
        is_mandatory: bool | None = None,
        default_dimension: str | None = None,
        default_description: str | None = None,
        active: bool | None = None,
    ) -> ValidationRuleTemplate:
        from datetime import UTC, datetime

        template = await self.get(template_id, workspace_id=workspace_id)
        if name is not None:
            if not name.strip():
                raise ValueError("name cannot be empty")
            if len(name) > 80:
                raise ValueError("name exceeds 80 characters")
            template.name = name.strip()
        if is_mandatory is not None:
            template.is_mandatory = is_mandatory
        if default_dimension is not None:
            template.default_dimension = default_dimension
        if default_description is not None:
            template.default_description = default_description
        if active is not None:
            template.active = active
        template.updated_at = datetime.now(UTC)
        return await self._repo.save(template)

    async def delete(self, template_id: UUID, *, workspace_id: UUID | None = None) -> None:
        # Verify ownership before deleting
        await self.get(template_id, workspace_id=workspace_id)
        await self._repo.delete(template_id)

    async def seed_for_work_item(
        self, workspace_id: UUID, work_item_type: str
    ) -> list[ValidationRuleTemplate]:
        """Return templates that would be seeded for a new work item of this type."""
        return await self._repo.list_matching(
            workspace_id=workspace_id,
            work_item_type=work_item_type,
        )
