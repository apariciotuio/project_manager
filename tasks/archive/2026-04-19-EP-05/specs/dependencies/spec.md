# EP-05 Dependencies Spec — US-053, US-054

## US-053 — Manage Functional Dependencies Between Tasks

**Actor**: Authenticated user with edit access to the work item.
**Precondition**: At least two `task_nodes` exist for the work item.

### Scenario 1: Add a dependency (A depends on B — B must complete before A)

WHEN the user sends POST `/api/v1/tasks/:task_id/dependencies` with `{ "depends_on_id": "uuid-b" }`
THEN the system runs DFS cycle detection on the full dependency graph for this work item with the proposed edge added
AND if no cycle is detected, inserts a row in `task_dependencies` with `task_id = A` and `depends_on_id = B`
AND returns HTTP 201 with the new dependency record
AND the `depends_on_id` task is now a predecessor of `task_id`

### Scenario 2: Add a dependency that creates a cycle

WHEN the user sends POST `/api/v1/tasks/:task_id/dependencies` with `{ "depends_on_id": "uuid-c" }` and this edge would create a cycle in the dependency DAG
THEN the system returns HTTP 422 with error code `DEPENDENCY_CYCLE_DETECTED`
AND includes in the response body the cycle path (ordered list of task IDs forming the cycle)
AND no row is inserted in `task_dependencies`

### Scenario 3: Add a self-dependency

WHEN the user sends POST `/api/v1/tasks/:task_id/dependencies` with `"depends_on_id"` equal to `task_id`
THEN the system returns HTTP 422 with error code `SELF_DEPENDENCY_FORBIDDEN`
AND no row is inserted

### Scenario 4: Add a dependency between tasks in different work items

WHEN the user sends POST `/api/v1/tasks/:task_id/dependencies` with a `depends_on_id` that belongs to a different `work_item_id`
THEN the system returns HTTP 422 with error code `CROSS_WORK_ITEM_DEPENDENCY_FORBIDDEN`
AND no row is inserted

### Scenario 5: Remove a dependency

WHEN the user sends DELETE `/api/v1/tasks/:task_id/dependencies/:depends_on_id`
THEN the system deletes the matching row in `task_dependencies`
AND returns HTTP 204
AND if no such dependency exists, returns HTTP 404

### Scenario 6: List dependencies for a task

WHEN the user sends GET `/api/v1/tasks/:task_id/dependencies`
THEN the response includes two lists: `predecessors` (tasks that must complete before this one) and `successors` (tasks that depend on this one)
AND each entry includes `task_id`, `title`, `status`, and `work_item_id`

### Scenario 7: Compute blocked tasks

WHEN the user sends GET `/api/v1/work-items/:id/tasks/blocked`
THEN the system traverses the full dependency graph for the work item
AND returns all task nodes where at least one predecessor has `status != done`
AND each blocked task entry includes `blocked_by`: list of predecessor task IDs that are not yet done
AND tasks with no predecessors are never in this list

### Scenario 8: Dependency removed when source task is deleted

WHEN a task node is deleted (via PATCH or split/merge operations)
THEN all `task_dependencies` rows where `task_id` or `depends_on_id` matches the deleted node are cascade-deleted
AND downstream tasks that were blocked only by the deleted node are no longer listed as blocked

---

## US-054 — View Unified Hierarchy

**Actor**: Authenticated user with read access.
**Precondition**: Work item exists (task tree may be empty).

### Scenario 1: Fetch full task tree for a work item

WHEN the user sends GET `/api/v1/work-items/:id/task-tree`
THEN the response returns a nested tree structure under `data.tree`
AND root-level nodes (parent_id = null) are ordered by `order` ascending
AND each node includes its `children` array, also ordered by `order` ascending
AND each node includes: `id`, `title`, `description`, `status`, `order`, `section_links`, `dependency_count` (number of predecessors), `is_blocked` (boolean, true if any predecessor not done)
AND the tree is computed in a single query using a recursive CTE (no N+1)

### Scenario 2: Empty task tree

WHEN the user sends GET `/api/v1/work-items/:id/task-tree` and no task nodes exist
THEN the response returns `data.tree: []`
AND HTTP 200 (not 404 — absence of tasks is a valid state)

### Scenario 3: Tree includes materialized path for breadcrumb navigation

WHEN the user sends GET `/api/v1/tasks/:task_id`
THEN the response includes `path`: an ordered list of ancestor node summaries (`id`, `title`) from root to parent
AND `path` is empty for root-level tasks
AND `path` allows the client to render breadcrumb navigation without additional requests

### Scenario 4: Navigate from specification section to tasks

WHEN the user views the specification (GET `/api/v1/work-items/:id/specification`)
THEN each section object includes `task_count`: number of task nodes referencing that section
AND `task_count` is computed as part of the specification query (no separate request required)

### Scenario 5: Tree view reflects dependency status

WHEN the user sends GET `/api/v1/work-items/:id/task-tree`
AND task B depends on task A (A is predecessor of B)
AND task A has `status = draft`
THEN task B appears with `is_blocked: true` in the tree response
AND task A appears with `is_blocked: false` (no predecessors or all done)

### Scenario 6: Tree depth limit

WHEN the task tree contains more than 3 levels of nesting (root → child → grandchild → great-grandchild)
THEN the system still returns the full tree without truncation at current target scale
AND the recursive CTE depth is bounded at 10 levels to prevent pathological inputs
AND nodes beyond depth 10 are omitted from the response with a `truncated: true` flag at the affected parent
