"""Mappers for TaskNode + TaskDependency — EP-05."""

from __future__ import annotations

from app.domain.models.task_node import TaskDependency, TaskGenerationSource, TaskNode, TaskStatus
from app.infrastructure.persistence.models.orm import TaskDependencyORM, TaskNodeORM


def task_node_to_domain(row: TaskNodeORM) -> TaskNode:
    return TaskNode(
        id=row.id,
        work_item_id=row.work_item_id,
        parent_id=row.parent_id,
        title=row.title,
        description=row.description,
        display_order=row.display_order,
        status=TaskStatus(row.status),
        generation_source=TaskGenerationSource(row.generation_source),
        materialized_path=row.materialized_path,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def task_node_to_orm(entity: TaskNode) -> TaskNodeORM:
    row = TaskNodeORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.parent_id = entity.parent_id
    row.title = entity.title
    row.description = entity.description
    row.display_order = entity.display_order
    row.status = entity.status.value
    row.generation_source = entity.generation_source.value
    row.materialized_path = entity.materialized_path
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    row.created_by = entity.created_by
    row.updated_by = entity.updated_by
    return row


def task_dependency_to_domain(row: TaskDependencyORM) -> TaskDependency:
    return TaskDependency(
        id=row.id,
        source_id=row.source_id,
        target_id=row.target_id,
        created_at=row.created_at,
        created_by=row.created_by,
    )


def task_dependency_to_orm(entity: TaskDependency) -> TaskDependencyORM:
    row = TaskDependencyORM()
    row.id = entity.id
    row.source_id = entity.source_id
    row.target_id = entity.target_id
    row.created_at = entity.created_at
    row.created_by = entity.created_by
    return row
