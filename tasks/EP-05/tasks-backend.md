# EP-05 Backend Tasks — Breakdown, Hierarchy & Dependencies

Tech stack: Python 3.12+, FastAPI, SQLAlchemy async, PostgreSQL 16+, Celery + Redis

---

## API Contract (interface with frontend)

### Task node response shape
```json
{
  "id": "uuid",
  "work_item_id": "uuid",
  "parent_id": "uuid | null",
  "title": "string",
  "description": "string",
  "display_order": 0,
  "status": "draft | in_progress | done",
  "generation_source": "llm | manual",
  "materialized_path": "uuid.uuid",
  "section_links": [{ "section_id": "uuid", "section_type": "string" }],
  "is_blocked": false,
  "blocked_by": ["uuid"],
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

### Tree response shape
```json
{
  "data": {
    "work_item_id": "uuid",
    "nodes": [
      {
        "id": "uuid",
        "title": "string",
        "status": "draft",
        "display_order": 0,
        "is_blocked": false,
        "section_links": [],
        "children": []
      }
    ]
  }
}
```

### Dependency response shape
```json
{
  "data": {
    "predecessors": [{ "id": "uuid", "title": "string", "status": "string" }],
    "successors": [{ "id": "uuid", "title": "string", "status": "string" }]
  }
}
```

### Error shapes
- 409: `{ "error": { "code": "BREAKDOWN_EXISTS", "message": "..." } }` — generate with `force=false` when tasks exist
- 422 cycle: `{ "error": { "code": "DEPENDENCY_CYCLE", "message": "...", "details": { "cycle_path": ["uuid", ...] } } }`
- 422 FSM: `{ "error": { "code": "INVALID_STATUS_TRANSITION", "message": "...", "details": { "blocked_by": ["uuid"] } } }`

---

## Phase 1 — Migrations

### Acceptance Criteria

See also: specs/breakdown/spec.md, specs/dependencies/spec.md

WHEN all Phase 1 migrations run in order
THEN `task_nodes`, `task_node_section_links`, and `task_dependencies` tables exist with all columns
AND `task_nodes.status` CHECK constraint rejects values outside `draft | in_progress | done`
AND `task_dependencies` CHECK constraint rejects `task_id = depends_on_id`
AND `task_node_section_links` UNIQUE rejects `(task_id, section_id)` duplicates
AND `task_dependencies` UNIQUE rejects duplicate `(task_id, depends_on_id)` edges
AND deleting a `task_nodes` row cascades to `task_node_section_links` and `task_dependencies`

WHEN the migration is rolled back
THEN all three tables are dropped without error

- [ ] 1.1 [RED] Write migration test: `task_nodes` table exists with all columns, CHECK constraints, and CASCADE behavior
- [ ] 1.2 [GREEN] Create Alembic migration: `task_nodes` table — `id`, `work_item_id`, `parent_id`, `title`, `description`, `display_order`, `status`, `generation_source`, `materialized_path`, `created_at`, `updated_at`, `created_by`, `updated_by`
- [ ] 1.3 [RED] Write migration test: `task_node_section_links` UNIQUE constraint on `(task_id, section_id)` rejects duplicate
- [ ] 1.4 [GREEN] Create Alembic migration: `task_node_section_links` table
- [ ] 1.5 [RED] Write migration test: `task_dependencies` CHECK constraint rejects `task_id = depends_on_id`; UNIQUE rejects duplicate edge
- [ ] 1.6 [GREEN] Create Alembic migration: `task_dependencies` table
- [ ] 1.7 [GREEN] Create all indexes: `idx_task_nodes_work_item_id`, `idx_task_nodes_parent_id`, `idx_task_nodes_mat_path` (gin trgm), `idx_tnsl_task_id`, `idx_tnsl_section_id`, `idx_task_dep_task_id`, `idx_task_dep_depends_on_id`
- [ ] 1.8 [RED] Write cascade delete test: deleting a `task_node` cascades to its `task_node_section_links` and `task_dependencies`

---

## Phase 2 — Domain Layer

### Acceptance Criteria

WHEN `TaskStatus.can_transition_to()` is called:
- `draft → in_progress` → `True`
- `in_progress → done` → `True`
- `done → draft` → `False`
- `draft → done` → `False`
- `in_progress → draft` → `False`

WHEN `TaskNode.transition_to(new_status)` is called with a blocked status
THEN `InvalidTransitionError` is raised with `blocked_by` list of predecessor IDs not yet `done`

WHEN `TaskNodeDraft.from_llm_response(data)` is called with valid JSON
THEN a `TaskNodeDraft` value object is returned with `title`, `description`, `section_type`
AND missing `section_type` key → `section_type = None` (not an error)
AND missing `title` key → raises `ValidationError`

### Enums and value objects

- [ ] 2.1 [RED] Write unit tests for `TaskStatus` FSM: `draft→in_progress` allowed, `in_progress→done` allowed, `done→draft` rejected, `draft→done` rejected
- [ ] 2.2 [GREEN] Implement `domain/models/task_node.py`: `TaskNode` entity with `can_transition_to(new_status: TaskStatus) -> bool`, status FSM enforcement in `transition_to()`
- [ ] 2.3 [RED] Write unit tests for `TaskNodeDraft` value object: valid LLM JSON parsed, missing `title` raises, `section_type` fallback to `None` when absent
- [ ] 2.4 [GREEN] Implement `domain/models/task_node_draft.py`: `TaskNodeDraft` value object with `from_llm_response(data: dict) -> TaskNodeDraft`
- [ ] Refactor: all repository methods must accept `workspace_id` as a required parameter — `get(task_id, workspace_id)`, `get_by_work_item(work_item_id, workspace_id)`, etc. Queries must include `WHERE workspace_id = :workspace_id` (join through `work_items` if `task_nodes` does not have a direct `workspace_id` column). Return `None` (not 403) on workspace mismatch to avoid existence disclosure (CRIT-2).
- [ ] 2.5 [GREEN] Define `domain/repositories/task_node_repository.py` interface: `get(id, workspace_id)`, `get_by_work_item(work_item_id, workspace_id)`, `count_by_work_item(work_item_id, workspace_id)`, `create`, `update`, `delete`, `get_tree_flat(work_item_id, workspace_id)`, `get_all_for_work_item(work_item_id, workspace_id)`
- [ ] 2.6 [GREEN] Define `domain/repositories/task_dependency_repository.py` interface: `get_by_work_item`, `create`, `delete`, `get_predecessors`, `get_successors`
- [ ] 2.7 [GREEN] Define `domain/repositories/task_section_link_repository.py` interface: `get_by_task`, `get_by_section`, `create_bulk`, `delete_by_task`

---

## Phase 3 — Cycle Detection (Pure Domain)

### Acceptance Criteria

See also: specs/dependencies/spec.md (US-053 Scenario 2, 3)

WHEN `has_cycle_after_add(edges, new_edge)` is called:
- Linear chain `A→B, B→C`, add `D→A` → `(False, [])`
- Triangle: `A→B, B→C`, add `C→A` → `(True, [C, A, B, C])` (full cycle path)
- Empty graph, add any non-self edge → `(False, [])`
- Self-loop: add `(A, A)` → `(True, [A])`
- The cycle path returned contains all node IDs forming the cycle in traversal order

WHEN the graph has 1000+ nodes
THEN the iterative DFS completes without exceeding Python's recursion limit

- [ ] 3.1 [RED] Write unit tests: no cycle in linear chain `A→B→C`, add `D→A` — no cycle
- [ ] 3.2 [RED] Write unit tests: triangle cycle — `A→B, B→C, add C→A` → `has_cycle=True`, path returned
- [ ] 3.3 [RED] Write unit test: empty graph — no cycle
- [ ] 3.4 [RED] Write unit test: single node attempted self-dependency → cycle path `[task_id]`
- [ ] 3.5 [RED] Write unit test: cycle path is correct — `target` node MUST be included in the returned cycle path (e.g. triangle `A→B, B→C, add C→A` must return path containing A, B, and C); path missing `target` is a correctness bug (Fixed per backend_review.md ALG-1)
- [ ] 3.6 [GREEN] Implement `domain/dependencies/cycle_detector.py`: `has_cycle_after_add(edges: list[tuple[UUID, UUID]], new_edge: tuple[UUID, UUID]) -> tuple[bool, list[UUID]]` — iterative DFS only (no recursion); explicitly append `target` to path before returning `True` to produce a complete cycle path
- [ ] 3.7 [REFACTOR] Ensure iterative (not recursive) DFS to avoid stack depth issues on large graphs; validate that cycle_path returned matches the `details.cycle_path` API contract in the 422 response

---

## Phase 4 — Infrastructure Layer

### Acceptance Criteria

**TaskNodeRepositoryImpl**

WHEN `create(node)` is called
THEN the row is persisted and returned with `materialized_path = work_item_id.node_id` for root nodes
AND `materialized_path = parent_materialized_path.node_id` for child nodes

WHEN `get_tree_flat(work_item_id)` is called
THEN a flat list is returned via recursive CTE with each row including `depth` (0 = root)
AND rows are ordered `(depth, display_order)` ascending
AND depth is capped at 10; nodes at depth 11+ are omitted and the depth-10 parent has `truncated=true`

WHEN `delete(task_id)` is called
THEN the row is deleted and all matching `task_node_section_links` and `task_dependencies` rows are removed via CASCADE

**TaskDependencyRepositoryImpl**

WHEN `get_by_work_item(work_item_id)` is called
THEN all edges within the work item are returned as `list[tuple[UUID, UUID]]` suitable for cycle detection

WHEN `create(task_id, depends_on_id)` is called with an existing duplicate
THEN a DB unique violation is raised (no silent ignore)

**LLM Breakdown Adapter**

WHEN valid LLM JSON with `{ "tasks": [...] }` is received
THEN a `list[TaskNodeDraft]` is returned

WHEN the JSON is malformed or the `tasks` key is absent
THEN `LLMParseError` is raised with the raw response captured

WHEN `tasks` is an empty array
THEN `[]` is returned (not an error)

### TaskNodeRepositoryImpl

- [ ] 4.1 [RED] Write repository tests: `create` persists and returns node with correct `materialized_path`, `get` returns node, `get_by_work_item` returns all nodes for work item
- [ ] 4.2 [GREEN] Implement `infrastructure/persistence/task_node_repository_impl.py` — async SQLAlchemy
- [ ] 4.3 [RED] Write repository test: `get_tree_flat` returns flat list via recursive CTE with `depth` metadata, `display_order` respected per level, depth capped at 10
- [ ] 4.4 [GREEN] Implement `get_tree_flat` using PostgreSQL `WITH RECURSIVE` CTE in `task_node_repository_impl.py`
- [ ] 4.5 [RED] Write repository test: `delete` cascades to section links and dependencies

### TaskDependencyRepositoryImpl

- [ ] 4.6 [RED] Write repository tests: `create` inserts edge, `delete` removes edge, `get_predecessors` returns correct nodes, `get_successors` returns correct nodes, `get_by_work_item` loads full graph for cycle detection
- [ ] 4.7 [GREEN] Implement `infrastructure/persistence/task_dependency_repository_impl.py`

### TaskSectionLinkRepositoryImpl

- [ ] 4.8 [RED] Write repository tests: `create_bulk` inserts multiple links, `get_by_task` returns all links, `delete_by_task` removes all links for a task
- [ ] 4.9 [GREEN] Implement `infrastructure/persistence/task_section_link_repository_impl.py`

### LLM Breakdown Adapter

- [ ] 4.10 [RED] Write unit tests for `BreakdownAdapter`: valid LLM JSON → `list[TaskNodeDraft]`, malformed JSON → raises `LLMParseError`, empty `tasks` array → returns `[]`, `section_type` absent → `TaskNodeDraft.section_type = None`
- [ ] 4.11 [GREEN] Implement `infrastructure/llm/adapters/breakdown_adapter.py` — reuse EP-03/EP-04 LLM client, use JSON mode / function calling
- [ ] 4.12 [GREEN] Implement `infrastructure/llm/prompts/breakdown_generation.py` — versioned prompt constant `BREAKDOWN_PROMPT_V1`

---

## Phase 5 — Application Services

### Acceptance Criteria — TaskService

See also: specs/breakdown/spec.md (US-050 Scenarios 1–5, US-051 Scenarios 1–8, US-052)

**generate(work_item_id, force)**

WHEN spec sections are non-empty and no tasks exist
THEN task nodes are created with `section_links`, status=`draft`, and HTTP 201 with full tree
AND `CompletenessCache.invalidate(work_item_id)` is called

WHEN tasks exist and `force=False`
THEN `ConflictError(409, BREAKDOWN_EXISTS)` is raised; no mutation occurs

WHEN `force=True`
THEN existing task nodes are deleted (CASCADE clears dependencies and section links) then regenerated
AND response includes `"replaced": true`

WHEN all spec sections have empty content
THEN `ValidationError(422, SPECIFICATION_EMPTY)` is raised; no LLM call made

WHEN the LLM adapter raises
THEN the transaction is rolled back; `502` with `BREAKDOWN_GENERATION_FAILED` returned

**split(task_id, title_a, description_a, title_b, description_b)**

WHEN called successfully
THEN original node is deleted in the same transaction
AND two new nodes created at original `display_order` and `display_order + 1`; siblings at higher positions shifted +1
AND `section_links` copied from original to both nodes
AND all `task_dependencies` referencing the original are removed
AND response contains both new node representations

WHEN `title_a` or `title_b` is missing
THEN `ValidationError(422)` with field-level errors; no mutation

**merge(source_ids, title, description)**

WHEN source_ids share the same parent and same work_item_id
THEN merged node created at `min(display_order)` of sources; siblings resequenced
AND `section_links` = deduplicated union of all source `section_links`
AND source nodes deleted; their dependencies removed
AND response includes merged node with all `section_ids`

WHEN source_ids have different parents
THEN `ValidationError(422, MERGE_CROSS_PARENT_FORBIDDEN)`; no mutation

WHEN fewer than 2 source_ids supplied
THEN `ValidationError(422)`

**reorder(work_item_id, ordered_ids)**

WHEN all IDs belong to the same parent level
THEN `display_order` reassigned as 1-indexed, gapless, matching the submitted sequence

WHEN any ID has a mismatched parent
THEN `ValidationError(422, INVALID_TASK_IDS)`

### Acceptance Criteria — DependencyService

See also: specs/dependencies/spec.md (US-053 Scenarios 1–7)

WHEN `add_dependency(task_id, depends_on_id)` creates a cycle
THEN `CyclicDependencyError(422, DEPENDENCY_CYCLE_DETECTED)` with `cycle_path: [uuid, ...]`

WHEN `add_dependency` with `task_id == depends_on_id`
THEN `ValidationError(422, SELF_DEPENDENCY_FORBIDDEN)`

WHEN `add_dependency` with tasks from different work items
THEN `ValidationError(422, CROSS_WORK_ITEM_DEPENDENCY_FORBIDDEN)`

WHEN `add_dependency` with a duplicate edge
THEN `ConflictError(409)`

WHEN `remove_dependency(task_id, depends_on_id)` and edge does not exist
THEN `NotFoundError(404)`

WHEN `get_blocked_tasks(work_item_id)` is called
THEN returns only tasks that have at least one predecessor with `status != done`
AND each result includes `blocked_by: [uuid, ...]` listing the non-done predecessor IDs
AND tasks with no predecessors are never included

### Acceptance Criteria — TaskTreeService

See also: specs/breakdown/spec.md (US-054 Scenarios 1–6)

WHEN `get_tree(work_item_id)` is called with no tasks
THEN response is `{ "work_item_id": "...", "nodes": [] }` with HTTP 200

WHEN nodes exist
THEN `is_blocked` is injected correctly (true iff any predecessor not `done`)
AND `children` arrays are ordered by `display_order` ascending at each level
AND `section_links` are populated from the in-memory node map (no extra DB query)

WHEN a node is at depth 2
THEN `breadcrumb = [root_title]`
WHEN at depth 3
THEN `breadcrumb = [root_title, level1_title]`
WHEN at root
THEN `breadcrumb = []`

### TaskService (CRUD, generate, split, merge, reorder)

- [ ] 5.1 [RED] Test `generate`: spec non-empty → creates task nodes with section links, returns list; spec empty → raises `ValidationError(422)`; tasks already exist + `force=False` → raises `ConflictError(409)`; `force=True` → deletes existing and regenerates; LLM failure → rolls back transaction
- [ ] 5.2 [GREEN] Implement `TaskService.generate(work_item_id: UUID, force: bool = False)`
- [ ] 5.3 [RED] Test `create`: valid `parent_id` → sets `materialized_path`; `section_ids` not belonging to work item → raises `ValidationError`; no `section_ids` → creates with no links
- [ ] 5.4 [GREEN] Implement `TaskService.create(work_item_id, parent_id, title, description, section_ids, actor_id)`
- [ ] 5.5 [RED] Test `update`: rename/description → persists; invalid FSM transition → raises `InvalidTransitionError(422)`; `in_progress→done` with incomplete predecessor → raises `ValidationError` with `blocked_by` list
- [ ] 5.6 [GREEN] Implement `TaskService.update(task_id, **fields)`
- [ ] 5.7 [RED] Test `reorder`: valid ordered_ids → updates `display_order` sequentially; IDs with mismatched parents → raises `ValidationError`; IDs not in work item → raises `NotFoundError`
- [ ] 5.8 [GREEN] Implement `TaskService.reorder(work_item_id, ordered_ids: list[UUID])`
- [ ] 5.9 [RED] Test `split`: original deleted, A/B created with same parent, sibling order shifted, section links copied to both, missing `title_a` or `title_b` → raises `ValidationError`
- [ ] 5.10 [GREEN] Implement `TaskService.split(task_id, title_a, description_a, title_b, description_b)` — single transaction
- [ ] 5.11 [RED] Test `merge`: merged node gets min order of sources, deduped section links, source nodes deleted, siblings resequenced; sources with different parents → raises `ValidationError`; single source → raises `ValidationError`
- [ ] 5.12 [GREEN] Implement `TaskService.merge(source_ids: list[UUID], title, description)` — single transaction
- [ ] 5.13 [RED] Test `update_section_links`: valid section_ids → replaces all links; invalid section_id for work item → raises `ValidationError`
- [ ] 5.14 [GREEN] Implement `TaskService.update_section_links(task_id, section_ids: list[UUID])`
- [ ] 5.15 [RED] Test completeness cache: `create()` and `delete()` each call `CompletenessCache.invalidate(work_item_id)`
- [ ] 5.16 [GREEN] Wire `CompletenessCache.invalidate()` calls in `TaskService.create()` and `TaskService.delete()`

### DependencyService

- [ ] 5.17 [RED] Test `add_dependency`: happy path inserts edge; cycle detected → raises `CyclicDependencyError(422)` with `cycle_path`; self-dependency → raises `ValidationError`; cross-work-item → raises `ValidationError`; duplicate edge → raises `ConflictError(409)`
- [ ] 5.18 [GREEN] Implement `DependencyService.add_dependency(task_id, depends_on_id)` — loads full graph, calls `cycle_detector.has_cycle_after_add`, inserts if no cycle
- [ ] 5.19 [RED] Test `remove_dependency`: exists → removes; not found → raises `NotFoundError(404)`
- [ ] 5.20 [GREEN] Implement `DependencyService.remove_dependency(task_id, depends_on_id)`
- [ ] 5.21 [RED] Test `get_blocked_tasks`: task with all predecessors `done` → not in result; task with one predecessor `in_progress` → in result with `blocked_by` list; no dependencies → empty list
- [ ] 5.22 [GREEN] Implement `DependencyService.get_blocked_tasks(work_item_id)`

### TaskTreeService

- [ ] 5.23 [RED] Test tree assembly: flat CTE result → correct nested dict; `is_blocked` flag injected correctly; `display_order` respected per level; empty work item → `nodes: []`
- [ ] 5.24 [GREEN] Implement `TaskTreeService.get_tree(work_item_id)` — fetch flat CTE result, assemble nested dict, inject `is_blocked` and `section_links`
- [ ] 5.25 [RED] Test breadcrumb: root node → `breadcrumb: []`; depth-2 node → `breadcrumb: [root_title]`; depth-3 → `breadcrumb: [root_title, level1_title]`
- [ ] 5.26 [GREEN] Implement breadcrumb from `materialized_path` (no extra DB query — resolve from in-memory node map)

---

## Phase 6 — Controllers

### Acceptance Criteria

See also: specs/breakdown/spec.md, specs/dependencies/spec.md

**POST /api/v1/work-items/{id}/tasks/generate**
- 201: `{ "data": { "nodes": [...], "replaced": false } }`
- 401: unauthenticated
- 403: no edit access to work item
- 404: work item not found
- 409: `BREAKDOWN_EXISTS` when tasks exist and `force=false`
- 422: `SPECIFICATION_EMPTY` when all sections empty
- 502: `BREAKDOWN_GENERATION_FAILED` on LLM error

**POST /api/v1/work-items/{id}/tasks** (create)
- 201: task node shape with `section_links: []` when no section_ids
- 403: no edit access
- 422: `section_ids` not belonging to work item

**GET /api/v1/tasks/{task_id}**
- 200: full task node shape including `section_links`, `breadcrumb`
- 401: unauthenticated
- 403: no read access
- 404: task not found

**PATCH /api/v1/tasks/{task_id}**
- 200: updated node shape
- 422: `INVALID_STATUS_TRANSITION` with `details.blocked_by` when transition blocked
- 404: not found
- 403: no edit access

**POST /api/v1/tasks/{task_id}/split**
- 201: `{ "data": { "a": {...}, "b": {...} } }`
- 422: field-level errors when `title_a` or `title_b` missing
- 404: task not found

**POST /api/v1/tasks/merge**
- 201: merged node shape with deduped `section_links`
- 422: `MERGE_CROSS_PARENT_FORBIDDEN` when parents differ
- 422: fewer than 2 source_ids

**PATCH /api/v1/work-items/{id}/tasks/reorder**
- 200: `{ "data": { "ordered_ids": [...] } }`
- 422: `INVALID_TASK_IDS` when IDs from mismatched parents or not in work item

**PATCH /api/v1/tasks/{task_id}/section-links**
- 200: task node with updated `section_links`
- 422: `INVALID_SECTION_ID` when any section_id not in work item

**GET /api/v1/work-items/{id}/sections/{section_id}/tasks**
- 200: list of task nodes referencing the section, ordered by `parent_id, display_order`
- 404: section not found

**POST /api/v1/tasks/{task_id}/dependencies**
- 201: `{ "data": { "task_id": "...", "depends_on_id": "..." } }`
- 422: `DEPENDENCY_CYCLE_DETECTED` with `details.cycle_path: ["uuid", ...]`
- 422: `SELF_DEPENDENCY_FORBIDDEN`
- 422: `CROSS_WORK_ITEM_DEPENDENCY_FORBIDDEN`
- 409: duplicate edge

**DELETE /api/v1/tasks/{task_id}/dependencies/{dep_id}**
- 204: success
- 404: edge not found

**GET /api/v1/tasks/{task_id}/dependencies**
- 200: `{ "data": { "predecessors": [...], "successors": [...] } }` each with `id, title, status`

**GET /api/v1/work-items/{id}/task-tree**
- 200: nested tree or `"nodes": []` for empty
- `is_blocked` correctly set on each node
- 404: work item not found

**GET /api/v1/work-items/{id}/tasks/blocked**
- 200: list of blocked task nodes with `blocked_by: [uuid, ...]`
- Empty list when no blocked tasks (not 404)

### task_controller.py (US-050, US-051, US-052)

- [ ] 6.1 [RED] Controller test `POST /api/v1/work-items/:id/tasks/generate`: 201 success shape, 409 exists, 422 empty spec, 502 LLM failure
- [ ] 6.2 [GREEN] Implement generate endpoint
- [ ] 6.3 [RED] Controller tests for `POST /tasks` (create), `GET /tasks/:id`, `PATCH /tasks/:id`, `DELETE /tasks/:id` — 201/200/204 success, 404 not found, 403 unauthorized
- [ ] 6.4 [GREEN] Implement CRUD endpoints
- [ ] 6.5 [RED] Controller tests for `POST /tasks/:id/split` and `POST /tasks/merge`: success shapes, 422 validation errors
- [ ] 6.6 [GREEN] Implement split and merge endpoints
- [ ] 6.7 [RED] Controller tests for `PATCH /work-items/:id/tasks/reorder`: 200 success, 422 mismatched parents
- [ ] 6.8 [GREEN] Implement reorder endpoint
- [ ] 6.9 [RED] Controller tests for `PATCH /tasks/:id/section-links`: 200 success, 422 invalid section
- [ ] 6.10 [GREEN] Implement section-links endpoint
- [ ] 6.11 [RED] Controller tests for `GET /work-items/:id/sections/:sid/tasks`
- [ ] 6.12 [GREEN] Implement section-to-tasks lookup endpoint

### task_dependency_controller.py (US-053)

- [ ] 6.13 [RED] Controller tests: `POST /tasks/:id/dependencies` 201 + cycle error shape (includes `cycle_path`), `DELETE /tasks/:id/dependencies/:dep_id` 204, `GET /tasks/:id/dependencies` list shape
- [ ] 6.14 [GREEN] Implement `task_dependency_controller.py`

### task_tree_controller.py (US-054)

- [ ] 6.15 [RED] Controller tests: `GET /work-items/:id/task-tree` full tree shape, empty tree `nodes: []`, `is_blocked` flags present, `GET /work-items/:id/tasks/blocked` list shape
- [ ] 6.16 [GREEN] Implement `task_tree_controller.py`

### Task search endpoint (for frontend TaskPickerCombobox)

- [ ] 6.17 [RED] Controller test: `GET /api/v1/work-items/:id/tasks/search?q=<text>` returns top 10 tasks by `title ILIKE '%q%'` within the work item; requires read access; `q` < 2 chars returns `[]` without DB query; 404 when work item not found
- [ ] 6.18 [GREEN] Add `TaskService.search_tasks(work_item_id: UUID, q: str) -> list[dict]` — ILIKE query on `task_nodes.title`, LIMIT 10, returns `[{id, title}]`
- [ ] 6.19 [GREEN] Implement `GET /api/v1/work-items/:id/tasks/search` in `task_controller.py`

**Response shape:** `{ "data": [{ "id": "uuid", "title": "string" }] }`

---

## Phase 7 — EP-04 Completeness Integration

### Acceptance Criteria

WHEN `check_breakdown(task_count=0)` is called
THEN `DimensionResult(filled=False)`

WHEN `check_breakdown(task_count=1)` or any positive integer
THEN `DimensionResult(filled=True)`

WHEN `CompletenessService.compute(work_item_id)` runs
THEN it calls `TaskNodeRepository.count_by_work_item(work_item_id)` and passes the result to `check_breakdown`
AND the `breakdown` dimension result reflects the current task count

- [ ] 7.1 [RED] Test `check_breakdown` dimension checker: `task_count=0` → `filled=False`; `task_count=1` → `filled=True`
- [ ] 7.2 [GREEN] Implement `check_breakdown(task_count: int) -> DimensionResult` in `domain/quality/dimension_checkers.py`
- [ ] 7.3 [RED] Test `CompletenessService.compute()` calls `TaskNodeRepository.count_by_work_item()` and passes result to `check_breakdown`
- [ ] 7.4 [GREEN] Update `CompletenessService` to inject `task_count` and pass to `check_breakdown`

---

## Phase 8 — Integration Tests

> **Concurrency note (per backend_review.md TC-2)**: `split()` and `merge()` shift sibling `display_order` values in the same transaction as the new node INSERTs. Under `READ COMMITTED` (SQLAlchemy async default), concurrent reads between INSERT and UPDATE can observe inconsistent `display_order`. This is acceptable at current scale. Do NOT cache `display_order` between mutation calls. If edit contention becomes an issue, add `SELECT FOR UPDATE` on the parent node before any child reorder. ⚠️ originally MVP-scoped — see decisions_pending.md

- [ ] 8.1 E2E: `generate` → `GET /task-tree` → `split` → `GET /task-tree` — verify tree structure changes correctly
- [ ] 8.2 E2E: `generate` → `add_dependency` → attempt cycle → verify 422 with `cycle_path`
- [ ] 8.3 E2E: `merge` two tasks → verify deduped section links in response → `GET /task-tree`
- [ ] 8.4 E2E: status transition to `done` blocked by undone predecessor → verify 422
- [ ] 8.5 E2E: completeness score changes when task nodes created — `breakdown` dimension flips from `False` to `True`
