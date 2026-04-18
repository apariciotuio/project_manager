"""EP-05 — DAG cycle detection for task_dependencies.

Pure DFS — O(V + E). Runs synchronously in DependencyService before insert.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID


def has_cycle_after_add(
    existing_edges: Iterable[tuple[UUID, UUID]],
    new_edge: tuple[UUID, UUID],
) -> bool:
    """Return True if adding `new_edge` (source -> target meaning source depends
    on target) to `existing_edges` creates a cycle.

    Edges are directed from source (dependent) to target (predecessor). A cycle
    exists if we can walk predecessor chains from `target` back to `source`.
    """
    if new_edge[0] == new_edge[1]:
        return True

    adjacency: dict[UUID, list[UUID]] = defaultdict(list)
    for source, target in existing_edges:
        adjacency[source].append(target)
    adjacency[new_edge[0]].append(new_edge[1])

    visited: set[UUID] = set()
    stack: list[UUID] = [new_edge[1]]
    target_of_new = new_edge[0]
    while stack:
        node = stack.pop()
        if node == target_of_new:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, []))
    return False
