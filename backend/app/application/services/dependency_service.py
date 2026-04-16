"""EP-05 — DependencyService.

Manages task_dependencies with cycle detection before insert.
"""
from __future__ import annotations

from uuid import UUID

from app.domain.models.task_node import TaskDependency
from app.domain.quality.cycle_detection import has_cycle_after_add
from app.domain.repositories.task_node_repository import (
    ITaskDependencyRepository,
    ITaskNodeRepository,
)


class DependencyCycleError(ValueError):
    pass


class DependencyNotFoundError(LookupError):
    pass


class DependencyService:
    def __init__(
        self,
        *,
        node_repo: ITaskNodeRepository,
        dep_repo: ITaskDependencyRepository,
    ) -> None:
        self._nodes = node_repo
        self._deps = dep_repo

    async def add(
        self,
        *,
        source_id: UUID,
        target_id: UUID,
        actor_id: UUID,
    ) -> TaskDependency:
        # Validate both nodes exist and belong to the same work item
        source = await self._nodes.get(source_id)
        if source is None:
            from app.application.services.task_service import TaskNodeNotFoundError

            raise TaskNodeNotFoundError(f"task node {source_id} not found")
        target = await self._nodes.get(target_id)
        if target is None:
            from app.application.services.task_service import TaskNodeNotFoundError

            raise TaskNodeNotFoundError(f"task node {target_id} not found")

        # Cycle detection over all edges in this work item
        edges = await self._deps.get_edges_for_work_item(source.work_item_id)
        existing: list[tuple[UUID, UUID]] = [(e.source_id, e.target_id) for e in edges]
        if has_cycle_after_add(existing, (source_id, target_id)):
            raise DependencyCycleError(
                f"adding dependency {source_id} -> {target_id} would create a cycle"
            )

        dep = TaskDependency.create(
            source_id=source_id,
            target_id=target_id,
            created_by=actor_id,
        )
        return await self._deps.add(dep)

    async def remove(self, dep_id: UUID) -> None:
        await self._deps.remove(dep_id)
