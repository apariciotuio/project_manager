"""In-memory fakes for ITaskNodeRepository, ITaskDependencyRepository, ITaskSectionLinkRepository."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.task_node import TaskDependency, TaskNode
from app.domain.repositories.task_node_repository import (
    ITaskDependencyRepository,
    ITaskNodeRepository,
    ITaskSectionLinkRepository,
)


class FakeTaskNodeRepository(ITaskNodeRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, TaskNode] = {}

    async def get(self, node_id: UUID) -> TaskNode | None:
        return self._store.get(node_id)

    async def get_by_work_item(self, work_item_id: UUID) -> list[TaskNode]:
        return [n for n in self._store.values() if n.work_item_id == work_item_id]

    async def count_by_work_item(self, work_item_id: UUID) -> int:
        return sum(1 for n in self._store.values() if n.work_item_id == work_item_id)

    async def save(self, node: TaskNode) -> TaskNode:
        self._store[node.id] = node
        return node

    async def delete(self, node_id: UUID) -> None:
        self._store.pop(node_id, None)

    async def get_tree_recursive(self, work_item_id: UUID) -> list[TaskNode]:
        nodes = [n for n in self._store.values() if n.work_item_id == work_item_id]
        return sorted(nodes, key=lambda n: (n.materialized_path, n.display_order))


class FakeTaskDependencyRepository(ITaskDependencyRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, TaskDependency] = {}

    async def get(self, dep_id: UUID) -> TaskDependency | None:
        return self._store.get(dep_id)

    async def get_by_source(self, source_id: UUID) -> list[TaskDependency]:
        return [d for d in self._store.values() if d.source_id == source_id]

    async def get_by_target(self, target_id: UUID) -> list[TaskDependency]:
        return [d for d in self._store.values() if d.target_id == target_id]

    async def get_edges_for_work_item(self, work_item_id: UUID) -> list[TaskDependency]:
        # Return all — in fakes we don't have work_item scope for deps
        return list(self._store.values())

    async def add(self, dep: TaskDependency) -> TaskDependency:
        self._store[dep.id] = dep
        return dep

    async def remove(self, dep_id: UUID) -> None:
        self._store.pop(dep_id, None)


class FakeTaskSectionLinkRepository(ITaskSectionLinkRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, list[UUID]] = {}  # task_id -> [section_id, ...]

    async def get_by_task(self, task_id: UUID) -> list[UUID]:
        return list(self._store.get(task_id, []))

    async def create_bulk(self, task_id: UUID, section_ids: list[UUID]) -> None:
        existing = self._store.get(task_id, [])
        for sid in section_ids:
            if sid not in existing:
                existing.append(sid)
        self._store[task_id] = existing

    async def delete_by_task(self, task_id: UUID) -> None:
        self._store.pop(task_id, None)
