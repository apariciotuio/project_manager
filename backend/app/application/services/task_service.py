"""EP-05 — TaskService.

Orchestrates TaskNode lifecycle: create, update, delete, move, and status FSM.
All tree mutations maintain materialized_path. Status transitions check predecessor
dependencies before allowing mark_done.
"""
from __future__ import annotations

from uuid import UUID

from app.domain.models.task_node import (
    TaskGenerationSource,
    TaskNode,
    TaskStatus,
)
from app.domain.repositories.task_node_repository import (
    ITaskDependencyRepository,
    ITaskNodeRepository,
)


class TaskNodeNotFoundError(LookupError):
    pass


class TaskCyclicDependencyError(ValueError):
    pass


class TaskService:
    def __init__(
        self,
        *,
        node_repo: ITaskNodeRepository,
        dep_repo: ITaskDependencyRepository,
    ) -> None:
        self._nodes = node_repo
        self._deps = dep_repo

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_or_404(self, node_id: UUID) -> TaskNode:
        node = await self._nodes.get(node_id)
        if node is None:
            raise TaskNodeNotFoundError(f"task node {node_id} not found")
        return node

    def _build_path(self, parent_path: str, node_id: UUID) -> str:
        """Append node_id to parent's materialized_path."""
        if parent_path:
            return f"{parent_path}.{node_id}"
        return str(node_id)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_node(
        self,
        *,
        work_item_id: UUID,
        parent_id: UUID | None,
        title: str,
        display_order: int,
        actor_id: UUID,
        description: str = "",
        source: TaskGenerationSource = TaskGenerationSource.MANUAL,
    ) -> TaskNode:
        parent_path = ""
        if parent_id is not None:
            parent = await self._get_or_404(parent_id)
            parent_path = parent.materialized_path

        node = TaskNode.create(
            work_item_id=work_item_id,
            parent_id=parent_id,
            title=title,
            display_order=display_order,
            created_by=actor_id,
            description=description,
            source=source,
        )
        # Set path after we have the id
        node.materialized_path = self._build_path(parent_path, node.id)
        return await self._nodes.save(node)

    async def update_node(
        self,
        *,
        node_id: UUID,
        title: str | None = None,
        description: str | None = None,
        actor_id: UUID,
    ) -> TaskNode:
        node = await self._get_or_404(node_id)
        if title is not None:
            node.title = title
        if description is not None:
            node.description = description
        from datetime import UTC, datetime

        node.updated_at = datetime.now(UTC)
        node.updated_by = actor_id
        return await self._nodes.save(node)

    async def delete_node(self, node_id: UUID) -> None:
        await self._get_or_404(node_id)
        await self._nodes.delete(node_id)

    async def move_node(
        self,
        *,
        node_id: UUID,
        new_parent_id: UUID | None,
        new_order: int,
        actor_id: UUID,
    ) -> TaskNode:
        node = await self._get_or_404(node_id)

        new_parent_path = ""
        if new_parent_id is not None:
            new_parent = await self._get_or_404(new_parent_id)
            new_parent_path = new_parent.materialized_path

        old_prefix = node.materialized_path
        new_prefix = self._build_path(new_parent_path, node.id)

        node.parent_id = new_parent_id
        node.display_order = new_order
        node.materialized_path = new_prefix

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        node.updated_at = now
        node.updated_by = actor_id
        await self._nodes.save(node)

        # Update descendants' paths
        descendants = await self._nodes.get_by_work_item(node.work_item_id)
        for desc in descendants:
            if desc.id == node.id:
                continue
            if desc.materialized_path.startswith(old_prefix + "."):
                desc.materialized_path = new_prefix + desc.materialized_path[len(old_prefix):]
                desc.updated_at = now
                desc.updated_by = actor_id
                await self._nodes.save(desc)

        return node

    # ------------------------------------------------------------------
    # Status FSM
    # ------------------------------------------------------------------

    async def start(self, *, node_id: UUID, actor_id: UUID) -> TaskNode:
        node = await self._get_or_404(node_id)
        node.start(actor_id)
        return await self._nodes.save(node)

    async def mark_done(self, *, node_id: UUID, actor_id: UUID) -> TaskNode:
        node = await self._get_or_404(node_id)
        # Collect status of all predecessors (nodes this one depends on)
        deps = await self._deps.get_by_source(node_id)
        predecessor_statuses: list[TaskStatus] = []
        for dep in deps:
            pred = await self._nodes.get(dep.target_id)
            if pred is not None:
                predecessor_statuses.append(pred.status)
        node.mark_done(actor_id, predecessor_statuses)
        return await self._nodes.save(node)

    async def reopen(self, *, node_id: UUID, actor_id: UUID) -> TaskNode:
        node = await self._get_or_404(node_id)
        node.reopen(actor_id)
        return await self._nodes.save(node)

    # ------------------------------------------------------------------
    # Tree query
    # ------------------------------------------------------------------

    async def get_tree(self, work_item_id: UUID) -> list[TaskNode]:
        return await self._nodes.get_tree_recursive(work_item_id)
