"""Mapper between WorkItem domain entity and WorkItemORM.

workspace_id is an infrastructure concern (multi-tenancy / RLS column) and is NOT
present on the domain WorkItem. The repository passes it explicitly when constructing
or updating ORM rows.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.models.work_item import WorkItem
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.persistence.models.orm import WorkItemORM


def to_domain(row: WorkItemORM) -> WorkItem:
    return WorkItem(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        type=WorkItemType(row.type),
        state=WorkItemState(row.state),
        owner_id=row.owner_id,
        creator_id=row.creator_id,
        description=row.description,
        original_input=row.original_input,
        priority=Priority(row.priority) if row.priority is not None else None,
        due_date=row.due_date,
        tags=list(row.tags) if row.tags else [],
        completeness_score=row.completeness_score,
        parent_work_item_id=row.parent_work_item_id,
        materialized_path=row.materialized_path,
        attachment_count=row.attachment_count,
        has_override=row.has_override,
        override_justification=row.override_justification,
        owner_suspended_flag=row.owner_suspended_flag,
        draft_data=dict(row.draft_data) if row.draft_data is not None else None,
        template_id=row.template_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        exported_at=row.exported_at,
        export_reference=row.export_reference,
    )


def to_orm(entity: WorkItem, *, workspace_id: UUID) -> WorkItemORM:
    row = WorkItemORM()
    row.id = entity.id
    apply_to_orm(entity, row, workspace_id=workspace_id)
    return row


def apply_to_orm(entity: WorkItem, row: WorkItemORM, *, workspace_id: UUID) -> None:
    """Apply domain entity fields onto an existing ORM row (used for UPDATE paths)."""
    row.workspace_id = workspace_id
    row.project_id = entity.project_id
    row.title = entity.title
    row.type = entity.type.value
    row.state = entity.state.value
    row.owner_id = entity.owner_id
    row.creator_id = entity.creator_id
    row.description = entity.description
    row.original_input = entity.original_input
    row.priority = entity.priority.value if entity.priority is not None else None
    row.due_date = entity.due_date
    row.tags = entity.tags
    row.completeness_score = entity.completeness_score
    row.parent_work_item_id = entity.parent_work_item_id
    row.materialized_path = entity.materialized_path
    row.attachment_count = entity.attachment_count
    row.has_override = entity.has_override
    row.override_justification = entity.override_justification
    row.owner_suspended_flag = entity.owner_suspended_flag
    row.draft_data = entity.draft_data
    row.template_id = entity.template_id
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.deleted_at = entity.deleted_at
    row.exported_at = entity.exported_at
    row.export_reference = entity.export_reference
