"""Mappers for Tag and WorkItemTag — EP-15."""

from __future__ import annotations

from app.domain.models.tag import Tag, WorkItemTag
from app.infrastructure.persistence.models.orm import TagORM, WorkItemTagORM


def tag_to_domain(row: TagORM) -> Tag:
    return Tag(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        color=row.color,
        archived_at=row.archived_at,
        created_at=row.created_at,
        created_by=row.created_by,
    )


def tag_to_orm(entity: Tag) -> TagORM:
    row = TagORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.name = entity.name
    row.color = entity.color
    row.archived_at = entity.archived_at
    row.created_at = entity.created_at
    row.created_by = entity.created_by
    return row


def work_item_tag_to_domain(row: WorkItemTagORM) -> WorkItemTag:
    return WorkItemTag(
        id=row.id,
        work_item_id=row.work_item_id,
        tag_id=row.tag_id,
        created_at=row.created_at,
        created_by=row.created_by,
    )


def work_item_tag_to_orm(entity: WorkItemTag) -> WorkItemTagORM:
    row = WorkItemTagORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.tag_id = entity.tag_id
    row.created_at = entity.created_at
    row.created_by = entity.created_by
    return row
