"""Mapper: ValidationRuleTemplate ↔ ValidationRuleTemplateORM — EP-10."""
from __future__ import annotations

from app.domain.models.validation_rule_template import ValidationRuleTemplate
from app.infrastructure.persistence.models.orm import ValidationRuleTemplateORM


def vrt_to_domain(row: ValidationRuleTemplateORM) -> ValidationRuleTemplate:
    return ValidationRuleTemplate(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        work_item_type=row.work_item_type,
        requirement_type=row.requirement_type,
        default_dimension=row.default_dimension,
        default_description=row.default_description,
        is_mandatory=row.is_mandatory,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def vrt_to_orm(entity: ValidationRuleTemplate) -> ValidationRuleTemplateORM:
    row = ValidationRuleTemplateORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.name = entity.name
    row.work_item_type = entity.work_item_type
    row.requirement_type = entity.requirement_type
    row.default_dimension = entity.default_dimension
    row.default_description = entity.default_description
    row.is_mandatory = entity.is_mandatory
    row.active = entity.active
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    return row
