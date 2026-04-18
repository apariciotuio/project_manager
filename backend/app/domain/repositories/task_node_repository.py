"""EP-05 — ITaskNodeRepository + ITaskDependencyRepository + ITaskSectionLinkRepository."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.task_node import TaskDependency, TaskNode


class ITaskNodeRepository(ABC):
    @abstractmethod
    async def get(self, node_id: UUID) -> TaskNode | None: ...

    @abstractmethod
    async def get_by_work_item(self, work_item_id: UUID) -> list[TaskNode]: ...

    @abstractmethod
    async def count_by_work_item(self, work_item_id: UUID) -> int: ...

    @abstractmethod
    async def save(self, node: TaskNode) -> TaskNode: ...

    @abstractmethod
    async def delete(self, node_id: UUID) -> None: ...

    @abstractmethod
    async def get_tree_recursive(self, work_item_id: UUID) -> list[TaskNode]:
        """Return all task nodes for a work item using WITH RECURSIVE CTE."""
        ...


class ITaskDependencyRepository(ABC):
    @abstractmethod
    async def get(self, dep_id: UUID) -> TaskDependency | None: ...

    @abstractmethod
    async def get_by_source(self, source_id: UUID) -> list[TaskDependency]: ...

    @abstractmethod
    async def get_by_target(self, target_id: UUID) -> list[TaskDependency]: ...

    @abstractmethod
    async def get_edges_for_work_item(self, work_item_id: UUID) -> list[TaskDependency]: ...

    @abstractmethod
    async def add(self, dep: TaskDependency) -> TaskDependency: ...

    @abstractmethod
    async def remove(self, dep_id: UUID) -> None: ...


class ITaskSectionLinkRepository(ABC):
    @abstractmethod
    async def get_by_task(self, task_id: UUID) -> list[UUID]:
        """Return section_ids linked to the task."""
        ...

    @abstractmethod
    async def create_bulk(self, task_id: UUID, section_ids: list[UUID]) -> None: ...

    @abstractmethod
    async def delete_by_task(self, task_id: UUID) -> None: ...
