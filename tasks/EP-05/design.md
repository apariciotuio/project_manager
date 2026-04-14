# EP-05 — Technical Design
# Breakdown, Hierarchy & Dependencies

---

## 1. Data Model

### 1.1 task_nodes

Adjacency list is the chosen tree strategy (see §2 for the rationale).
Traceability to multiple spec sections (post-merge) requires a join table rather than a single FK column.

```sql
CREATE TABLE task_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES task_nodes(id) ON DELETE CASCADE,
    title           VARCHAR(512) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    display_order   SMALLINT NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
        -- allowed: 'draft' | 'in_progress' | 'done'
    generation_source VARCHAR(16) NOT NULL DEFAULT 'llm',
        -- 'llm' | 'manual'
    materialized_path TEXT NOT NULL DEFAULT '',
        -- dot-separated UUID chain: "parent_uuid.grandparent_uuid"
        -- root nodes: '' (empty string)
        -- maintained by application layer on insert/move
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID NOT NULL REFERENCES users(id),
    updated_by      UUID NOT NULL REFERENCES users(id)
);

CREATE INDEX idx_task_nodes_work_item_id ON task_nodes(work_item_id);
CREATE INDEX idx_task_nodes_parent_id    ON task_nodes(parent_id);
-- For path-prefix breadcrumb lookups:
CREATE INDEX idx_task_nodes_mat_path     ON task_nodes USING gin(materialized_path gin_trgm_ops);
```

`status` FSM (enforced in application layer, not DB constraint):
- `draft` → `in_progress` (allowed anytime)
- `in_progress` → `done` (blocked if any predecessor is not `done`)
- No reverse FSM transitions. Re-opening a completed task uses the explicit endpoint
  `POST /api/v1/tasks/:id/unmark-done` (resolution #20) — it flips `status` back to `in_progress`,
  emits a `task.reopened` event, and writes a timeline entry.

### 1.2 task_node_section_links

Many-to-many between task nodes and spec sections. One-to-one at generation time (one section per task),
but merge operations produce multiple links on a single task node.

```sql
CREATE TABLE task_node_section_links (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID NOT NULL REFERENCES task_nodes(id) ON DELETE CASCADE,
    section_id  UUID NOT NULL REFERENCES work_item_sections(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_task_section_link UNIQUE (task_id, section_id)
);

CREATE INDEX idx_tnsl_task_id    ON task_node_section_links(task_id);
CREATE INDEX idx_tnsl_section_id ON task_node_section_links(section_id);
```

Replacing the single `section_id` FK on `task_nodes` with this join table is the only design that handles
both the normal case (one section) and the merge case (N sections) without nullable FKs or JSON blobs.

### 1.3 task_dependencies

Explicit DAG edges. **Cross-work-item dependencies are allowed** (resolution #20). The DAG validation is global: any cycle across the workspace (not only within one work item) is rejected at insert time. Columns renamed to `source_id` / `target_id` to reflect that the edge no longer scopes to a single work item.

```sql
CREATE TABLE task_dependencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID NOT NULL REFERENCES task_nodes(id) ON DELETE CASCADE,
        -- the dependent task (waits for target)
    target_id       UUID NOT NULL REFERENCES task_nodes(id) ON DELETE CASCADE,
        -- the predecessor task
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID NOT NULL REFERENCES users(id),

    CONSTRAINT uq_task_dependency UNIQUE (source_id, target_id),
    CONSTRAINT no_self_dependency  CHECK (source_id != target_id)
);

CREATE INDEX idx_task_dep_source ON task_dependencies(source_id);
CREATE INDEX idx_task_dep_target ON task_dependencies(target_id);
```

**Cross-work-item dependency allowed**: `source_id` and `target_id` may belong to different work items (same workspace). Cycle detection runs a global DFS across all `task_dependencies` edges in the workspace.

---

## 2. Tree Structure: Adjacency List + Materialized Path

**Decision: adjacency list with maintained materialized path. Reject nested sets.**

Nested sets provide fast subtree reads but make every insert/move/delete a multi-row update across the
entire table. With concurrent edits (split, merge, reorder happening simultaneously) that becomes a
locking nightmare. Nested sets are correct only for read-heavy, write-rare trees. A task breakdown is
edited constantly.

Adjacency list alone requires a recursive CTE for tree reads — acceptable. PostgreSQL's `WITH RECURSIVE`
handles this cleanly and the tree depth is bounded (10 levels hard cap).

The materialized path column is maintained by the application layer (not triggers) on every insert and
parent-change. It enables O(1) ancestor lookup and breadcrumb construction without a recursive query.
Path format: `"uuid-root.uuid-level1.uuid-level2"` (ancestor chain, closest-to-root first).

For the full tree read (`GET /work-items/:id/task-tree`), a single recursive CTE fetches the entire
tree, the Python layer assembles the nested dict. This avoids N+1 completely.

---

## 3. Cycle Detection Algorithm

Runs synchronously inside `DependencyService.add_dependency()` before any DB insert.
Runtime: O(V + E) where V and E are the task and dependency counts for the work item. Both are small
(tens to low hundreds). No async needed.

```python
def has_cycle_after_add(
    edges: list[tuple[UUID, UUID]],  # existing (task_id, depends_on_id) pairs
    new_edge: tuple[UUID, UUID],
) -> tuple[bool, list[UUID]]:
    """
    DFS from new_edge[1] (the proposed predecessor).
    If we can reach new_edge[0] (the dependent) via existing edges + new_edge,
    a cycle exists. Returns (cycle_found, cycle_path).
    """
    graph: dict[UUID, list[UUID]] = defaultdict(list)
    for task_id, dep_id in edges:
        graph[dep_id].append(task_id)  # successor direction
    graph[new_edge[1]].append(new_edge[0])

    target = new_edge[1]
    start = new_edge[0]

    visited: set[UUID] = set()
    path: list[UUID] = []

    def dfs(node: UUID) -> bool:
        if node in visited:
            return False
        if node == target:
            path.append(node)
            return True
        visited.add(node)
        path.append(node)
        for successor in graph[node]:
            if dfs(successor):
                return True
        path.pop()
        return False

    found = dfs(start)
    return found, path if found else []
```

> **NOTE (Fixed per backend_review.md ALG-1)**: The sample code above is illustrative only and has a known bug — the `target` node is appended to `path` before `visited.add(target)`, meaning if `target` is encountered it is appended correctly but the code above uses recursive DFS which can hit Python's recursion limit on large graphs. Implementation MUST use iterative DFS (mandated in task 3.6/3.7). The iterative implementation must explicitly append `target` to the cycle path when detected (before returning `True`) to produce a complete cycle path. The recursive sample is NOT to be used verbatim.

The cycle path is returned to the API layer and included in the 422 response body (US-053 Scenario 2).

---

## 4. Split Operation

`TaskService.split(task_id, title_a, description_a, title_b, description_b)`:

1. Load source task node. Verify it belongs to the requesting user's accessible work item.
2. Load all `task_node_section_links` for source task (typically one entry).
3. Begin transaction:
   a. Create node A: same `parent_id`, `work_item_id`, `generation_source = 'manual'`, `order = source.order`, title/description from input.
   b. Create node B: same parent, `order = source.order + 1`, title/description from input.
   c. Shift all sibling nodes with `order >= source.order + 1` by +1 (excluding A and B).
   d. Insert `task_node_section_links` for both A and B, copying all links from source node.
   e. Delete source node (cascades `task_dependencies` — see §1.3).
   f. Update materialized paths for A and B.
4. Commit. Return both new nodes.

Dependencies on the source node are intentionally dropped. Inheriting them automatically would silently
create potentially incorrect dependency semantics. The user re-adds relevant dependencies explicitly.

---

## 5. Merge Operation

`TaskService.merge(source_ids, title, description)`:

1. Load all source task nodes. Validate: same `work_item_id`, same `parent_id`. Reject if not.
2. Collect all `task_node_section_links` across all source nodes — deduplicate on `section_id`.
3. Begin transaction:
   a. Determine `min_order` = minimum `display_order` among source nodes.
   b. Create merged node: same `parent_id`, `work_item_id`, `order = min_order`, `status = draft`, `generation_source = 'manual'`.
   c. Insert `task_node_section_links` for merged node (all deduplicated section IDs).
   d. Delete all source nodes (cascades their `task_dependencies`).
   e. Reorder remaining siblings to close gaps (re-sequence `display_order` from 1).
   f. Update materialized path for merged node.
4. Commit. Return merged node with all `section_links`.

Same reasoning as split: dependency links are dropped on merge. Users re-establish them.

---

## 6. API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST   | /api/v1/work-items/:id/tasks/generate          | LLM breakdown. Body: `{ force?: bool }`. 409 if exists, 422 if spec empty. |
| GET    | /api/v1/work-items/:id/task-tree               | Full nested tree. Recursive CTE + Python assembly. |
| POST   | /api/v1/work-items/:id/tasks                   | Manual task creation. `section_ids` optional. |
| PATCH  | /api/v1/tasks/:task_id                         | Update title, description, status. |
| DELETE | /api/v1/tasks/:task_id                         | Delete node + cascade. |
| PATCH  | /api/v1/work-items/:id/tasks/reorder           | Body: `{ ordered_ids: [uuid] }`. Validates same parent. |
| POST   | /api/v1/tasks/:task_id/split                   | Body: title_a/b, description_a/b. Returns both new nodes. |
| POST   | /api/v1/tasks/merge                            | Body: `{ source_ids, title, description }`. |
| PATCH  | /api/v1/tasks/:task_id/section-links           | Replace section links. Body: `{ section_ids }`. |
| GET    | /api/v1/tasks/:task_id                         | Single node with section_links and path (breadcrumb). |
| GET    | /api/v1/work-items/:id/sections/:sid/tasks     | Tasks referencing a specific section. |
| POST   | /api/v1/tasks/:task_id/dependencies            | Body: `{ depends_on_id }`. Cycle detection runs here. |
| DELETE | /api/v1/tasks/:task_id/dependencies/:dep_id    | Remove dependency edge. |
| GET    | /api/v1/tasks/:task_id/dependencies            | Predecessors + successors. |
| GET    | /api/v1/work-items/:id/tasks/blocked           | All blocked tasks with `blocked_by` lists. |

All endpoints require Bearer JWT. PATCH/POST/DELETE additionally require owner or editor role on the
work item, checked in the service layer.

Additional endpoint for reverse status (resolution #20):
| Method | Path | Notes |
|---|---|---|
| POST | /api/v1/tasks/:id/unmark-done | Reopens a `done` task back to `in_progress`; emits `task.reopened`; writes timeline entry. |

Drag-and-drop reordering on the frontend uses **`dnd-kit`** (resolution #20) — no `react-beautiful-dnd`.

### Concurrency

Default isolation level is **READ COMMITTED**. Hot-path service methods (`reorder`, `split`, `merge`) wrap their work item's sibling set in `SELECT ... FOR UPDATE` only when contention is observed (demand-driven upgrade). No advisory locks; no SERIALIZABLE.

---

## 7. Breakdown Generation via Dundun

> **Resolved 2026-04-14 (decisions_pending.md #20, #32)**: Task breakdown is delegated to Dundun. Our backend owns no LLM SDK, no prompt registry, and no breakdown prompt template. We call Dundun asynchronously via the Celery + callback pattern.

Flow:
1. Controller `POST /api/v1/work-items/:id/tasks/generate` enqueues a Celery task on queue `dundun`.
2. The Celery task calls `DundunClient.invoke_agent(agent="wm_breakdown_agent", user_id=..., work_item_id=..., callback_url=<BE>/api/v1/dundun/callback, payload={ specification_content })`. Dundun responds 202 with a `request_id`.
3. Dundun invokes `POST /api/v1/dundun/callback` with the structured response when generation completes.
4. The callback handler persists `TaskNodeDraft`s, creates `task_nodes` rows, and emits `tasks.generated` on the event bus for the UI to consume via SSE.

Dundun returns structured output matching this schema (owned by Dundun, not redefined here):
```json
{
  "tasks": [
    { "title": "string", "description": "string", "section_type": "string",
      "subtasks": [ { "title": "string", "description": "string" } ] }
  ]
}
```

`section_type` maps to the source `work_item_sections` row. If the section type does not exist, the task node is created with no section link (graceful degradation).

No synchronous path, no polling loop. The UI subscribes to the SSE stream for live updates. Latency is bounded by Dundun's SLA.

---

## 8. Integration with EP-04 Completeness Engine

EP-04's completeness engine defines a `breakdown` dimension. This dimension is `filled = True` when
the work item has at least one non-draft `task_node` (i.e., at least one task in `in_progress` or
`done` state, OR at least N task nodes regardless of status — TBD with product, default: any task
node present means "breakdown started").

Currently: `breakdown` dimension is `filled = True` if `COUNT(task_nodes WHERE work_item_id = ?) > 0`.

Integration point: `TaskService.create()` and `TaskService.delete()` call
`CompletenessCache.invalidate(work_item_id)` after committing, identical to how `SectionService.save()`
does it in EP-04. No direct coupling to EP-04 business logic — only the cache invalidation hook.

The `check_breakdown` dimension checker function (pure, in `domain/quality/dimension_checkers.py`)
receives `task_count: int` (injected by `CompletenessService`) and returns `DimensionResult`.
`CompletenessService.compute()` fetches `task_count` via `TaskNodeRepository.count_by_work_item()`.

---

## 9. Layer Breakdown

```
presentation/
  controllers/
    task_controller.py              # US-050/051/052 endpoints
    task_dependency_controller.py   # US-053 endpoints
    task_tree_controller.py         # US-054 tree endpoint

application/
  services/
    task_service.py                 # generate, create, update, split, merge, reorder, delete
    dependency_service.py           # add, remove, list, blocked computation
    task_tree_service.py            # tree assembly from recursive CTE result

domain/
  models/
    task_node.py                    # TaskNode entity + status FSM
    task_node_draft.py              # Value object from LLM response
    task_tree.py                    # Assembled tree value object (for response serialization)
  repositories/
    task_node_repository.py         # interface
    task_dependency_repository.py   # interface

infrastructure/
  persistence/
    task_node_repository_impl.py    # adjacency list queries, recursive CTE
    task_dependency_repository_impl.py
    task_section_link_repository_impl.py
  dundun/
    dundun_client.py                # HTTP + WS client, used here via Celery
    breakdown_callback_handler.py   # consumes POST /api/v1/dundun/callback for wm_breakdown_agent results
```

---

## 10. Alternatives Considered

**Nested sets for tree storage**: Rejected. Insert/update/delete requires O(n) row updates. Concurrent
split/merge/reorder operations serialize on a full-table rewrite. Adjacency list + CTE is correct and
safe here.

**Storing cycle-detection result in DB**: Rejected. The graph is small and changes frequently. Run DFS
in Python on every add — it's fast enough and keeps the DB simple.

**Inheriting dependencies after split/merge**: Rejected. Automatic inheritance silently assigns
potentially wrong semantics. User explicitly re-adds what applies. Transparent is better than magic.

**Cross-work-item dependencies**: Rejected. Adds inter-work-item locking, cascades, and UI
complexity. Scope to same work item. Revisit later. ⚠️ originally MVP-scoped — see decisions_pending.md

**Storing `section_ids` as a PostgreSQL array on `task_nodes`**: Rejected. Arrays are not queryable by
element without special indexing, and referential integrity (FK) cannot be enforced on array elements.
The join table is the right tool.
