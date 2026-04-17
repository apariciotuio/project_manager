"""EP-10 — ValidationRuleTemplate SQLAlchemy repository impl."""
from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.validation_rule_template import ValidationRuleTemplate
from app.domain.repositories.validation_rule_template_repository import (
    IValidationRuleTemplateRepository,
)
from app.infrastructure.persistence.mappers.validation_rule_template_mapper import (
    vrt_to_domain,
    vrt_to_orm,
)
from app.infrastructure.persistence.models.orm import ValidationRuleTemplateORM


class ValidationRuleTemplateRepositoryImpl(IValidationRuleTemplateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, template: ValidationRuleTemplate) -> ValidationRuleTemplate:
        self._session.add(vrt_to_orm(template))
        await self._session.flush()
        return template

    async def get(self, template_id: UUID) -> ValidationRuleTemplate | None:
        row = await self._session.get(ValidationRuleTemplateORM, template_id)
        return vrt_to_domain(row) if row else None

    async def list_for_workspace(
        self, workspace_id: UUID
    ) -> list[ValidationRuleTemplate]:
        stmt = (
            sa.select(ValidationRuleTemplateORM)
            .where(
                ValidationRuleTemplateORM.workspace_id == workspace_id,
                ValidationRuleTemplateORM.active.is_(True),
            )
            .order_by(
                ValidationRuleTemplateORM.is_mandatory.desc(),
                ValidationRuleTemplateORM.name,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [vrt_to_domain(r) for r in rows]

    async def list_matching(
        self,
        *,
        workspace_id: UUID,
        work_item_type: str | None,
    ) -> list[ValidationRuleTemplate]:
        """Active templates matching workspace + type (including globals + type-agnostic)."""
        conditions: list[sa.ColumnElement] = [
            ValidationRuleTemplateORM.active.is_(True),
            sa.or_(
                ValidationRuleTemplateORM.workspace_id == workspace_id,
                ValidationRuleTemplateORM.workspace_id.is_(None),  # global templates
            ),
        ]
        if work_item_type is not None:
            conditions.append(
                sa.or_(
                    ValidationRuleTemplateORM.work_item_type == work_item_type,
                    ValidationRuleTemplateORM.work_item_type.is_(None),
                )
            )

        stmt = (
            sa.select(ValidationRuleTemplateORM)
            .where(*conditions)
            .order_by(
                ValidationRuleTemplateORM.is_mandatory.desc(),
                ValidationRuleTemplateORM.name,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [vrt_to_domain(r) for r in rows]

    async def save(self, template: ValidationRuleTemplate) -> ValidationRuleTemplate:
        existing = await self._session.get(ValidationRuleTemplateORM, template.id)
        if existing is None:
            self._session.add(vrt_to_orm(template))
        else:
            existing.name = template.name
            existing.work_item_type = template.work_item_type
            existing.requirement_type = template.requirement_type
            existing.default_dimension = template.default_dimension
            existing.default_description = template.default_description
            existing.is_mandatory = template.is_mandatory
            existing.active = template.active
            existing.updated_at = template.updated_at
        await self._session.flush()
        return template

    async def delete(self, template_id: UUID) -> None:
        row = await self._session.get(ValidationRuleTemplateORM, template_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()
