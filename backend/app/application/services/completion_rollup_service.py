"""EP-05 — CompletionRollupService.

Derives rollup_status for each node based on its descendants' statuses.
Pure service — no DB access, no side effects, computes on demand.

Rollup logic:
  - If node has no children → rollup='draft' (leaf node)
  - If all descendants status='done' → rollup='done'
  - If any descendant status='in_progress' → rollup='in_progress'
  - Else → rollup='draft'
"""
from __future__ import annotations

from typing import Any

from app.domain.models.task_node import TaskNode, TaskStatus


class CompletionRollupService:
    """Stateless service — construct once, reuse freely."""

    def compute_rollup(
        self,
        node: TaskNode,
        direct_and_indirect_descendants: list[TaskNode],
    ) -> str:
        """Compute rollup_status for *node* given its descendants list.

        Args:
            node: the node whose rollup we are computing
            direct_and_indirect_descendants: all descendants (any depth) of node
        """
        if not direct_and_indirect_descendants:
            return "draft"

        statuses = [d.status for d in direct_and_indirect_descendants]

        if all(s is TaskStatus.DONE for s in statuses):
            return "done"
        if any(s is TaskStatus.IN_PROGRESS for s in statuses):
            return "in_progress"
        return "draft"

    def enrich_tree(self, all_nodes: list[TaskNode]) -> list[dict[str, Any]]:
        """Return a flat list of dicts, one per node, each with rollup_status injected.

        Descendants for each node are derived from materialized_path:
        a node D is a descendant of P if D.materialized_path starts with P's path + ".".

        This is O(N²) — acceptable at current scale (task trees are bounded to ~200 nodes).
        """
        result: list[dict[str, Any]] = []
        for node in all_nodes:
            prefix = node.materialized_path + "."
            descendants = [
                n for n in all_nodes
                if n.id != node.id and n.materialized_path.startswith(prefix)
            ]
            rollup = self.compute_rollup(node, descendants)
            result.append({
                "id": str(node.id),
                "work_item_id": str(node.work_item_id),
                "parent_id": str(node.parent_id) if node.parent_id else None,
                "title": node.title,
                "description": node.description,
                "display_order": node.display_order,
                "status": node.status.value,
                "generation_source": node.generation_source.value,
                "materialized_path": node.materialized_path,
                "rollup_status": rollup,
                "created_at": node.created_at.isoformat(),
                "updated_at": node.updated_at.isoformat(),
                "created_by": str(node.created_by),
                "updated_by": str(node.updated_by),
            })
        return result
