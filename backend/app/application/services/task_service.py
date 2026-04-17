"""EP-05 — TaskService.

Orchestrates TaskNode lifecycle: create, update, delete, move, split, merge,
reorder, and status FSM. All tree mutations maintain materialized_path. Status
transitions check predecessor dependencies before allowing mark_done.
"""
from __future__ import annotations

from uuid import UUID

from app.domain.models.task_node import (
    TaskGenerationSource,
    TaskNode,
    TaskStatus,
)
from app.domain.ports.cache import ICache
from app.domain.repositories.task_node_repository import (
    ITaskDependencyRepository,
    ITaskNodeRepository,
    ITaskSectionLinkRepository,
)


class TaskNodeNotFoundError(LookupError):
    pass


class TaskCyclicDependencyError(ValueError):
    pass


def _completeness_cache_key(work_item_id: UUID) -> str:
    return f"completeness:{work_item_id}"


class TaskService:
    def __init__(
        self,
        *,
        node_repo: ITaskNodeRepository,
        dep_repo: ITaskDependencyRepository,
        link_repo: ITaskSectionLinkRepository | None = None,
        cache: ICache | None = None,
    ) -> None:
        self._nodes = node_repo
        self._deps = dep_repo
        self._links = link_repo
        self._cache = cache

    async def _invalidate_completeness(self, work_item_id: UUID) -> None:
        if self._cache is not None:
            await self._cache.delete(_completeness_cache_key(work_item_id))

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
        saved = await self._nodes.save(node)
        await self._invalidate_completeness(work_item_id)
        return saved

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
        node = await self._get_or_404(node_id)
        await self._nodes.delete(node_id)
        await self._invalidate_completeness(node.work_item_id)

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

    # ------------------------------------------------------------------
    # Single node + breadcrumb (EP-05 Commit 2)
    # ------------------------------------------------------------------

    async def get_node_with_breadcrumb(
        self, node_id: UUID
    ) -> tuple[TaskNode, list[dict]] | None:
        """Return (node, breadcrumb) where breadcrumb = [{id, title}, ...] root→parent.

        Breadcrumb is derived from materialized_path without extra DB queries:
        split path segments (UUIDs), look each up in the flat node list for
        this work item, return in order (root first, parent last).
        """
        node = await self._nodes.get(node_id)
        if node is None:
            return None

        # materialized_path = "uuid.uuid.uuid" — segments are ancestor IDs
        path = node.materialized_path or ""
        segments = path.split(".") if path else []
        # Last segment is the node itself — drop it
        ancestor_ids = segments[:-1]

        if not ancestor_ids:
            return node, []

        # Fetch all nodes for this work item to build a lookup map
        siblings = await self._nodes.get_by_work_item(node.work_item_id)
        id_to_node = {str(n.id): n for n in siblings}

        breadcrumb = []
        for seg in ancestor_ids:
            anc = id_to_node.get(seg)
            if anc is not None:
                breadcrumb.append({"id": str(anc.id), "title": anc.title})

        return node, breadcrumb

    # ------------------------------------------------------------------
    # Search (EP-05 Commit 2)
    # ------------------------------------------------------------------

    async def search_tasks(
        self, *, work_item_id: UUID, q: str
    ) -> list[dict]:
        """Return [{id, title}] for tasks whose title ILIKE '%q%' within work_item.

        Returns [] without DB query when len(q) < 2.
        Limited to 10 results.
        """
        if len(q) < 2:
            return []

        nodes = await self._nodes.get_by_work_item(work_item_id)
        q_lower = q.lower()
        results = [
            {"id": str(n.id), "title": n.title}
            for n in nodes
            if q_lower in n.title.lower()
        ]
        return results[:10]

    # ------------------------------------------------------------------
    # Split
    # ------------------------------------------------------------------

    async def split(
        self,
        *,
        task_id: UUID,
        title_a: str,
        title_b: str,
        actor_id: UUID,
        description_a: str = "",
        description_b: str = "",
    ) -> tuple[TaskNode, TaskNode]:
        """Split source into two siblings. Source is deleted."""
        if not title_a or not title_a.strip():
            raise ValueError("title_a must not be empty")
        if not title_b or not title_b.strip():
            raise ValueError("title_b must not be empty")

        source = await self._get_or_404(task_id)
        section_ids: list[UUID] = []
        if self._links is not None:
            section_ids = await self._links.get_by_task(task_id)

        from datetime import UTC, datetime
        now = datetime.now(UTC)

        node_a = TaskNode.create(
            work_item_id=source.work_item_id,
            parent_id=source.parent_id,
            title=title_a.strip(),
            display_order=source.display_order,
            created_by=actor_id,
            description=description_a,
            source=TaskGenerationSource.MANUAL,
        )
        node_a.materialized_path = self._build_path(
            self._parent_path(source), node_a.id
        )

        node_b = TaskNode.create(
            work_item_id=source.work_item_id,
            parent_id=source.parent_id,
            title=title_b.strip(),
            display_order=source.display_order + 1,
            created_by=actor_id,
            description=description_b,
            source=TaskGenerationSource.MANUAL,
        )
        node_b.materialized_path = self._build_path(
            self._parent_path(source), node_b.id
        )

        await self._nodes.save(node_a)
        await self._nodes.save(node_b)

        if self._links is not None and section_ids:
            await self._links.create_bulk(node_a.id, section_ids)
            await self._links.create_bulk(node_b.id, section_ids)

        await self._nodes.delete(task_id)
        await self._invalidate_completeness(source.work_item_id)

        return node_a, node_b

    def _parent_path(self, node: TaskNode) -> str:
        """Return the materialized_path of the parent by stripping the last segment."""
        if not node.materialized_path:
            return ""
        parts = node.materialized_path.rsplit(".", 1)
        return parts[0] if len(parts) > 1 else ""

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    async def merge(
        self,
        *,
        source_ids: list[UUID],
        title: str,
        actor_id: UUID,
        description: str = "",
    ) -> TaskNode:
        """Merge sources (same parent) into one new node. Sources are deleted."""
        if len(source_ids) < 2:
            raise ValueError("merge requires at least 2 source_ids")

        sources: list[TaskNode] = []
        for sid in source_ids:
            node = await self._nodes.get(sid)
            if node is None:
                raise TaskNodeNotFoundError(f"task node {sid} not found")
            sources.append(node)

        # Validate same parent
        parent_ids = {n.parent_id for n in sources}
        if len(parent_ids) > 1:
            raise ValueError(
                "cannot merge nodes with different parents (MERGE_CROSS_PARENT_FORBIDDEN)"
            )

        # Collect + deduplicate section links
        all_section_ids: list[UUID] = []
        if self._links is not None:
            seen: set[UUID] = set()
            for src in sources:
                for sid in await self._links.get_by_task(src.id):
                    if sid not in seen:
                        seen.add(sid)
                        all_section_ids.append(sid)

        min_order = min(n.display_order for n in sources)
        common_parent_id = next(iter(parent_ids))
        sample = sources[0]

        # Compute parent path from sample node
        merged_parent_path = self._parent_path(sample)

        merged = TaskNode.create(
            work_item_id=sample.work_item_id,
            parent_id=common_parent_id,
            title=title,
            display_order=min_order,
            created_by=actor_id,
            description=description,
            source=TaskGenerationSource.MANUAL,
        )
        merged.materialized_path = self._build_path(merged_parent_path, merged.id)
        await self._nodes.save(merged)

        if self._links is not None and all_section_ids:
            await self._links.create_bulk(merged.id, all_section_ids)

        for src in sources:
            await self._nodes.delete(src.id)
        await self._invalidate_completeness(sample.work_item_id)

        return merged

    # ------------------------------------------------------------------
    # Reorder
    # ------------------------------------------------------------------

    async def reorder(
        self,
        *,
        work_item_id: UUID,
        ordered_ids: list[UUID],
        actor_id: UUID,
    ) -> list[TaskNode]:
        """Reassign display_order to ordered_ids (1-indexed, gapless).
        All IDs must exist in work_item and share the same parent_id.
        """
        from datetime import UTC, datetime
        nodes_by_id: dict[UUID, TaskNode] = {}
        for nid in ordered_ids:
            node = await self._nodes.get(nid)
            if node is None or node.work_item_id != work_item_id:
                raise TaskNodeNotFoundError(f"task node {nid} not found in work item")
            nodes_by_id[nid] = node

        parent_ids = {n.parent_id for n in nodes_by_id.values()}
        if len(parent_ids) > 1:
            raise ValueError("all reordered nodes must share the same parent_id")

        now = datetime.now(UTC)
        result: list[TaskNode] = []
        for i, nid in enumerate(ordered_ids, start=1):
            node = nodes_by_id[nid]
            node.display_order = i
            node.updated_at = now
            node.updated_by = actor_id
            await self._nodes.save(node)
            result.append(node)

        return result
