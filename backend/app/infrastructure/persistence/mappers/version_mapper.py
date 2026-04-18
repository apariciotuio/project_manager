"""Mapper for WorkItemVersion — EP-07."""

from __future__ import annotations

from app.domain.models.work_item_version import (
    VersionActorType,
    VersionTrigger,
    WorkItemVersion,
)
from app.infrastructure.persistence.models.orm import WorkItemVersionORM


def version_to_domain(row: WorkItemVersionORM) -> WorkItemVersion:
    return WorkItemVersion(
        id=row.id,
        work_item_id=row.work_item_id,
        version_number=row.version_number,
        snapshot=dict(row.snapshot),
        created_by=row.created_by,
        created_at=row.created_at,
        snapshot_schema_version=row.snapshot_schema_version,
        trigger=VersionTrigger(row.trigger),
        actor_type=VersionActorType(row.actor_type),
        actor_id=row.actor_id,
        commit_message=row.commit_message,
        archived=row.archived,
        workspace_id=row.workspace_id,
    )


def version_to_orm(entity: WorkItemVersion) -> WorkItemVersionORM:
    row = WorkItemVersionORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.version_number = entity.version_number
    row.snapshot = entity.snapshot
    row.created_by = entity.created_by
    row.created_at = entity.created_at
    row.snapshot_schema_version = entity.snapshot_schema_version
    row.trigger = entity.trigger.value
    row.actor_type = entity.actor_type.value
    row.actor_id = entity.actor_id
    row.commit_message = entity.commit_message
    row.archived = entity.archived
    if entity.workspace_id is not None:
        row.workspace_id = entity.workspace_id
    return row
