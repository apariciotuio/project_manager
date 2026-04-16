"""EP-05 — TaskNodeRepositoryImpl + TaskDependencyRepositoryImpl."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.task_node import TaskDependency, TaskNode
from app.domain.repositories.task_node_repository import (
    ITaskDependencyRepository,
    ITaskNodeRepository,
)
from app.infrastructure.persistence.mappers.task_node_mapper import (
    task_dependency_to_domain,
    task_dependency_to_orm,
    task_node_to_domain,
    task_node_to_orm,
)
from app.infrastructure.persistence.models.orm import TaskDependencyORM, TaskNodeORM

_RECURSIVE_CTE = text(
    """
    WITH RECURSIVE cte AS (
        SELECT *
        FROM task_nodes
        WHERE work_item_id = :work_item_id
          AND parent_id IS NULL
        UNION ALL
        SELECT tn.*
        FROM task_nodes tn
        JOIN cte ON tn.parent_id = cte.id
    )
    SELECT id FROM cte
    ORDER BY materialized_path, display_order
    """
)


class TaskNodeRepositoryImpl(ITaskNodeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, node_id: UUID) -> TaskNode | None:
        row = await self._session.get(TaskNodeORM, node_id)
        return task_node_to_domain(row) if row else None

    async def get_by_work_item(self, work_item_id: UUID) -> list[TaskNode]:
        stmt = (
            select(TaskNodeORM)
            .where(TaskNodeORM.work_item_id == work_item_id)
            .order_by(TaskNodeORM.materialized_path, TaskNodeORM.display_order)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [task_node_to_domain(r) for r in rows]

    async def save(self, node: TaskNode) -> TaskNode:
        existing = await self._session.get(TaskNodeORM, node.id)
        if existing is None:
            self._session.add(task_node_to_orm(node))
        else:
            existing.parent_id = node.parent_id
            existing.title = node.title
            existing.description = node.description
            existing.display_order = node.display_order
            existing.status = node.status.value
            existing.generation_source = node.generation_source.value
            existing.materialized_path = node.materialized_path
            existing.updated_at = node.updated_at
            existing.updated_by = node.updated_by
        await self._session.flush()
        return node

    async def delete(self, node_id: UUID) -> None:
        await self._session.execute(
            delete(TaskNodeORM).where(TaskNodeORM.id == node_id)
        )
        await self._session.flush()

    async def get_tree_recursive(self, work_item_id: UUID) -> list[TaskNode]:
        result = await self._session.execute(
            _RECURSIVE_CTE, {"work_item_id": work_item_id}
        )
        ids = [row[0] for row in result]
        if not ids:
            return []
        stmt = select(TaskNodeORM).where(TaskNodeORM.id.in_(ids))
        rows_map = {
            r.id: r
            for r in (await self._session.execute(stmt)).scalars().all()
        }
        # Preserve ordering from CTE
        return [task_node_to_domain(rows_map[i]) for i in ids if i in rows_map]


class TaskDependencyRepositoryImpl(ITaskDependencyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_source(self, source_id: UUID) -> list[TaskDependency]:
        stmt = select(TaskDependencyORM).where(
            TaskDependencyORM.source_id == source_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [task_dependency_to_domain(r) for r in rows]

    async def get_edges_for_work_item(self, work_item_id: UUID) -> list[TaskDependency]:
        """Return all dependency edges whose source node belongs to work_item_id."""
        stmt = (
            select(TaskDependencyORM)
            .join(TaskNodeORM, TaskDependencyORM.source_id == TaskNodeORM.id)
            .where(TaskNodeORM.work_item_id == work_item_id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [task_dependency_to_domain(r) for r in rows]

    async def add(self, dep: TaskDependency) -> TaskDependency:
        self._session.add(task_dependency_to_orm(dep))
        await self._session.flush()
        return dep

    async def remove(self, dep_id: UUID) -> None:
        await self._session.execute(
            delete(TaskDependencyORM).where(TaskDependencyORM.id == dep_id)
        )
        await self._session.flush()
