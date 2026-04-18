"""Mappers for Project, RoutingRule — EP-10."""

from __future__ import annotations

from app.domain.models.project import Project, RoutingRule
from app.infrastructure.persistence.models.orm import ProjectORM, RoutingRuleORM


def project_to_domain(row: ProjectORM) -> Project:
    return Project(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
    )


def project_to_orm(entity: Project) -> ProjectORM:
    row = ProjectORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.name = entity.name
    row.description = entity.description
    row.deleted_at = entity.deleted_at
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.created_by = entity.created_by
    return row


def routing_rule_to_domain(row: RoutingRuleORM) -> RoutingRule:
    return RoutingRule(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        work_item_type=row.work_item_type,
        suggested_team_id=row.suggested_team_id,
        suggested_owner_id=row.suggested_owner_id,
        suggested_validators=list(row.suggested_validators),
        priority=row.priority,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
    )


def routing_rule_to_orm(entity: RoutingRule) -> RoutingRuleORM:
    row = RoutingRuleORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.project_id = entity.project_id
    row.work_item_type = entity.work_item_type
    row.suggested_team_id = entity.suggested_team_id
    row.suggested_owner_id = entity.suggested_owner_id
    row.suggested_validators = entity.suggested_validators  # type: ignore[assignment]  # JSON col; ORM annotates as dict but stores list
    row.priority = entity.priority
    row.active = entity.active
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.created_by = entity.created_by
    return row
