# EP-14 — Backend Subtasks

**Status (archived 2026-04-18 as v1)**: ✅ SHIPPED — Parent-FK plumbing (migrations 0030/0031, WorkItemType enum incl. MILESTONE + STORY, domain field `parent_work_item_id`, create endpoint accepts + threads it through service, GET `/work-items?parent_work_item_id=<uuid>` returns direct children). Frontend hierarchy UI (tree view, breadcrumb, parent picker, rollup badge, ancestor/children hooks, DnD reparent on task_nodes) 100% shipped with 48 tests green.

> **⚠️ EP-14 v1 scope (archived)**: FK plumbing + FE UI. Internally coherent because the REST surface has no reparent endpoint — an external client cannot mutate hierarchy via the public API.
>
> **⚠️ Known data-corruption hole (v1 only, requires v2 before prod rollout of any reparent feature)**: create-path does NOT validate hierarchy rules (parent-type compatibility, cycle prevention) or populate `materialized_path`. A compromised backend instance or raw-SQL-capable client can insert cycles (A→B→A) or invalid parent-type links (e.g. Story under Bug). TreeQueryService would then malfunction (infinite loop on ancestor fetch, wrong rollup aggregation). v2 **MUST** implement HierarchyValidator + cycle detection BEFORE merging the PATCH reparent endpoint.

### v2 scope (new follow-up epic, tracked separately — NOT EP-14 v1)
- BE-14-03: `HierarchyValidator` — parent-type rules for all 11 types per `HIERARCHY_RULES` (`backend/app/domain/value_objects/work_item_type.py:28-46`).
- BE-14-04: `MaterializedPathService` — compute + bulk-update on insert/reparent via SQL CTE.
- BE-14-05: Repo method `bulk_update_materialized_paths` — single SQL statement, no N+1.
- BE-14-06: Cycle detection — O(1) check against materialized_path string.
- BE-14-07: Amend create to call HierarchyValidator, compute path, do cross-scope checks.
- BE-14-08: `PATCH /work-items/{id}` reparent endpoint + MaterializedPathService integration.
- BE-14-09: Delete guard — block deletion with children; emit event for path cleanup.
- BE-14-10: `CompletionRollupService` — parent completeness as weighted aggregate of children.
- BE-14-11: `TreeQueryService` — `get_ancestors`, `get_children`, `get_descendants_by_ancestor` (zero N+1).
- BE-14-12: Hierarchy controller — `GET /projects/{id}/hierarchy`, `/work-items/{id}/children`, `/ancestors`, `/rollup`.
- BE-14-13: Amend create/update endpoints — add parent validation errors (422).
- BE-14-14: List endpoint ancestor filter — `?ancestor_id=<uuid>` via materialized_path LIKE.
- BE-14-15: Rollup cache invalidation Celery task — handles state_changed, parent_changed, created, deleted events.

All work is workspace-scoped. Every service method and repository query must filter by `workspace_id`. No cross-workspace data access is permitted.

TDD markers: RED = failing test first, GREEN = implementation, REFACTOR = clean up.

---

**Unchecked items below are the v2 scope.** They remained on the original 2026-04-13 plan because v1 was scoped-down to parent FK + FE UI only; the algorithms are deferred to the follow-up epic listed above.

---

## Group 1: Database Migration

### BE-14-01: Migration — alter work_items table
- [ ] Write migration `EP-14_001_hierarchy_columns.sql`
  - [x] Drop old `work_items_type_valid` CHECK constraint (migration 0031, `backend/migrations/versions/0031_extend_work_item_types.py:36`)
  - [x] Add updated CHECK including `'milestone'`, `'story'` — shipped via `ADD CONSTRAINT ... NOT VALID` + `VALIDATE CONSTRAINT` for zero-downtime (`backend/migrations/versions/0031_extend_work_item_types.py:39-43`)
  - [x] Add `parent_work_item_id UUID REFERENCES work_items(id) ON DELETE RESTRICT` (nullable) — shipped in earlier migration 0030 (`backend/migrations/versions/0030_ep14_ep15_ep16_ep17.py`)
  - [ ] Add `materialized_path TEXT NOT NULL DEFAULT ''`
  - [ ] Add indexes: `idx_work_items_parent_id`, `idx_work_items_mat_path` (GIN trigram), `idx_work_items_ws_parent`
- [ ] Verify migration runs clean on a fresh DB and on a DB with existing work_items rows
- [ ] Verify existing rows have `parent_work_item_id = NULL` and `materialized_path = ''` after migration
- Acceptance: migration is idempotent-safe (UP only; DOWN drops columns and restores old CHECK)

---

## Group 2: Domain Model + Enum Extension

### BE-14-02: Extend WorkItemType enum and WorkItem entity
- [ ] RED: test that `WorkItemType.MILESTONE` and `WorkItemType.STORY` exist and are serialised as `"milestone"` and `"story"`
- [x] GREEN: add values to `WorkItemType` enum in `domain/models/work_item.py` — already present in domain value object; ORM `_WORK_ITEM_TYPES` also synced (`backend/app/infrastructure/persistence/models/orm.py:208`)
- [ ] RED: test that `WorkItem` dataclass accepts `parent_work_item_id: UUID | None` and `materialized_path: str`
- [ ] GREEN: add fields to `WorkItem`
  - [x] **Partial:** `parent_work_item_id: UUID | None` is on the domain model + ORM + mapper (`backend/app/domain/models/work_item.py`, `backend/app/infrastructure/persistence/mappers/work_item_mapper.py`). `materialized_path` NOT shipped.
- [ ] REFACTOR: ensure existing tests still pass (no field regressions)
- Acceptance: type check passes with `strict: true` equivalent (mypy --strict); no `Any` introduced

---

## Group 3: HierarchyValidator

### BE-14-03: Implement HierarchyValidator
- [ ] RED: test `validate_parent(MILESTONE, any_non_none)` returns `(False, "HIERARCHY_INVALID_PARENT_TYPE")`
- [ ] RED: test `validate_parent(EPIC, MILESTONE)` returns `(True, None)`
- [ ] RED: test `validate_parent(EPIC, EPIC)` returns `(False, "HIERARCHY_INVALID_PARENT_TYPE")`
- [ ] RED: test `validate_parent(STORY, EPIC)` returns `(True, None)`
- [ ] RED: test `validate_parent(STORY, INITIATIVE)` returns `(True, None)`
- [ ] RED: test `validate_parent(STORY, MILESTONE)` returns `(False, ...)`
- [ ] RED: test `validate_parent(STORY, STORY)` returns `(False, ...)`
- [ ] RED: test `validate_parent(TASK, MILESTONE)` returns `(True, None)` — flexible type
- [ ] RED: test `validate_parent(TASK, STORY)` returns `(True, None)`
- [ ] RED: test `validate_parent(any_type, None)` returns `(True, None)` for all types
- [ ] RED: test all 11 types for the None parent case
- [ ] GREEN: implement `domain/hierarchy/hierarchy_validator.py`
- [ ] REFACTOR: triangulate — add boundary tests for `REQUIREMENT`, `ENHANCEMENT`, `BUG`, `IDEA`, `SPIKE`, `BUSINESS_CHANGE`
- Acceptance: 100% branch coverage on `validate_parent`; pure function — no mocks needed

---

## Group 4: MaterializedPathService

### BE-14-04: Implement MaterializedPathService
- [ ] RED: test `compute_path(None)` returns `""`
- [ ] RED: test `compute_path(parent_id)` where parent has `materialized_path = ""` returns `str(parent_id)`
- [ ] RED: test `compute_path(parent_id)` where parent has `materialized_path = "A"` returns `"A.<parent_id>"`
- [ ] RED: test `compute_path(parent_id)` where parent has `materialized_path = "A.B"` returns `"A.B.<parent_id>"`
- [ ] GREEN: implement `compute_path` with fake repository
- [ ] RED: test `update_subtree_paths` calls `bulk_update_materialized_paths` exactly once with correct args
- [ ] RED: test subtree update with 1 level of children: child paths recomputed correctly
- [ ] RED: test subtree update with 2 levels: grandchild paths recomputed correctly
- [ ] RED: test reparenting an item from path "A.B" to "C" updates item and all descendants
- [ ] GREEN: implement `update_subtree_paths` — delegates to repository
- [ ] REFACTOR: ensure fake repository used throughout; no DB calls in unit tests
- Acceptance: all path manipulations are pure string operations; no recursion in Python (one SQL call)

### BE-14-05: Implement repository method bulk_update_materialized_paths
- [ ] RED: integration test — create parent + child, call `bulk_update_materialized_paths`, verify child path updated in DB
- [ ] RED: integration test — 3-level tree, update root, verify all descendants updated
- [ ] RED: integration test — verify workspace scoping: only descendants within workspace affected
- [ ] GREEN: implement `WITH RECURSIVE` CTE UPDATE in `work_item_repository_impl.py`
  - CTE fetches all descendants of `root_id`
  - Replaces old path prefix with new prefix in one `UPDATE ... FROM`
- Acceptance: single SQL statement (EXPLAIN confirms no sequential scan on unindexed paths)

---

## Group 5: Cycle Detection

### BE-14-06: Implement cycle detection utility
- [ ] RED: test `would_create_cycle(item_id, "")` returns `False`
- [ ] RED: test `would_create_cycle(item_id, str(item_id))` returns `True` — self in path
- [ ] RED: test `would_create_cycle(A, "B.A.C")` returns `True` — A in proposed parent's path
- [ ] RED: test `would_create_cycle(A, "B.C")` returns `False`
- [ ] RED: test self-reference: `new_parent_id == item_id` returns `True` before path check
- [ ] GREEN: implement `domain/hierarchy/cycle_detection.py`
- Acceptance: pure function; O(1) — no DB calls

---

## Group 6: WorkItemService Amendments

### BE-14-07: Amend create_work_item to handle parent assignment
- [ ] RED: test create with `parent_work_item_id` calls `HierarchyValidator.validate_parent`
- [ ] RED: test create with invalid parent type raises `HierarchyValidationError`
- [ ] RED: test create with parent in different workspace raises `HierarchyValidationError` (code: CROSS_WORKSPACE)
- [ ] RED: test create with parent in different project raises `HierarchyValidationError` (code: CROSS_PROJECT)
- [ ] RED: test create with soft-deleted parent raises `HierarchyValidationError` (code: PARENT_NOT_FOUND)
- [ ] RED: test create with valid parent computes and sets `materialized_path`
- [ ] RED: test create with `type=milestone` and non-null parent raises error
- [ ] GREEN: implement validation + path computation in `WorkItemService.create_work_item`
  - [x] **Partial (propagation only):** `CreateWorkItemCommand.parent_work_item_id` field (`backend/app/application/commands/create_work_item_command.py:26`); controller accepts it on `POST /api/v1/work-items` (`backend/app/presentation/controllers/work_item_controller.py:92`); request schema exposes it (`backend/app/presentation/schemas/work_item_schemas.py:46`). **No** `HierarchyValidator`, cycle detection, path computation, or cross-scope checks yet.
- [ ] REFACTOR: extract workspace+project cross-check into private `_validate_parent_scope` method

### BE-14-08: Amend update_work_item to handle reparenting
- [ ] RED: test update with new `parent_work_item_id` runs cycle detection
- [ ] RED: test self-reference raises `HierarchyValidationError` (code: CYCLE_DETECTED)
- [ ] RED: test descendant-as-parent raises `HierarchyValidationError` (code: CYCLE_DETECTED)
- [ ] RED: test valid reparent calls `MaterializedPathService.update_subtree_paths` in same transaction
- [ ] RED: test valid reparent emits `work_item.parent_changed` event with old and new paths
- [ ] RED: test reparent to `null` resets path to `""` for item and descendants
- [ ] GREEN: implement in `WorkItemService.update_work_item`
- [ ] REFACTOR: transaction boundary — path update + event emit must be atomic

### BE-14-09: Amend delete_work_item to block deletion when children exist
- [ ] RED: test delete with children raises `HierarchyHasChildrenError` with child count in details
- [ ] RED: test delete with no children proceeds normally (existing soft-delete logic)
- [ ] GREEN: add `has_children` check before soft-delete in `WorkItemService.delete_work_item`
- Acceptance: `ON DELETE RESTRICT` in DB is last line of defence; application layer must catch this first

---

## Group 7: CompletionRollupService

### BE-14-10: Implement CompletionRollupService
- [ ] RED: test `get_rollup` returns cached value from Redis without DB call when cache hit
- [ ] RED: test `get_rollup` calls `_compute_and_cache` on cache miss
- [ ] RED: test `_compute_and_cache` returns `None` for leaf node (no children)
- [ ] RED: test `_compute_and_cache` with all-draft children returns 0
- [ ] RED: test `_compute_and_cache` with all-ready children returns 100
- [ ] RED: test `_compute_and_cache` with mixed states: 2 ready + 1 in_clarification + 1 draft → 53
- [ ] RED: test `_compute_and_cache` for parent with child that has its own rollup (uses cached rollup not state weight)
- [ ] RED: test `invalidate` deletes Redis keys for all ancestor UUIDs in `materialized_path`
- [ ] RED: test `invalidate` with empty `materialized_path` deletes no keys (no error)
- [ ] RED: test `invalidate` is idempotent (calling twice on same path does not error)
- [ ] GREEN: implement `CompletionRollupService`
- [ ] REFACTOR: use fake Redis (in-memory dict) in unit tests; no real Redis dependency
- Acceptance: STATE_WEIGHTS dict covers all 7 states; KeyError impossible

---

## Group 8: TreeQueryService

### BE-14-11: Implement TreeQueryService
- [ ] RED: test `get_ancestors` for root item returns `[]`
- [ ] RED: test `get_ancestors` for item with path `"A.B"` returns `[A, B]` in order
- [ ] RED: test `get_ancestors` calls repo with `id IN (A, B)` — one DB query, not two
- [ ] RED: test `get_ancestors` returns items in path order (closest-to-root first)
- [ ] GREEN: implement `get_ancestors` — parse `materialized_path`, bulk-fetch in one query, reorder by path position
- [ ] RED: test `get_children` returns only direct children (parent_work_item_id = item_id), workspace-scoped
- [ ] RED: test `get_children` returns empty page for leaf node
- [ ] RED: test `get_children` is paginated (cursor)
- [ ] GREEN: implement `get_children`
- [ ] RED: integration test `get_project_hierarchy`: returns roots + unparented + nested children correctly
- [ ] RED: integration test hierarchy truncated at 200 roots with `meta.truncated = true`
- [ ] RED: integration test hierarchy depth limit at 10 levels
- [ ] GREEN: implement `get_project_hierarchy` using `WITH RECURSIVE` CTE
- [ ] RED: test `get_descendants_by_ancestor` uses `materialized_path LIKE '%<uuid>%'`
- [ ] RED: test `get_descendants_by_ancestor` with type filter
- [ ] RED: test `get_descendants_by_ancestor` with state filter
- [ ] RED: test ancestor not in results (only its descendants)
- [ ] GREEN: implement `get_descendants_by_ancestor`
- Acceptance: zero N+1 queries — EXPLAIN on test DB must show single query per service method call

---

## Group 9: API Endpoints

### BE-14-12: Hierarchy controller + routes
- [ ] RED: test `GET /api/v1/projects/:id/hierarchy` returns 200 with correct shape
- [ ] RED: test endpoint returns 403 for wrong workspace
- [ ] RED: test cursor pagination: `?cursor=<token>&limit=50`
- [ ] RED: test `GET /api/v1/work-items/:id/children` returns 200
- [ ] RED: test `GET /api/v1/work-items/:id/ancestors` returns breadcrumb
- [ ] RED: test `GET /api/v1/work-items/:id/rollup` returns 200 with rollup_percent
- [ ] RED: test rollup null for leaf node
- [ ] GREEN: implement `presentation/controllers/hierarchy_controller.py`
- [ ] REFACTOR: response schemas as Pydantic models (no dict returns from controllers)

### BE-14-13: Amend work-items create/update endpoints
- [ ] RED: test `POST /work-items` with `parent_work_item_id` — validates and sets
- [ ] RED: test `POST /work-items` with invalid parent type — 422 with error code
- [ ] RED: test `PATCH /work-items/:id` with new `parent_work_item_id` — triggers subtree update
- [ ] RED: test `PATCH /work-items/:id` with `parent_work_item_id: null` — detaches
- [ ] GREEN: amend `work_item_controller.py` and request schemas
  - [x] **Partial (create only):** `POST /work-items` accepts and persists `parent_work_item_id` (`backend/app/presentation/schemas/work_item_schemas.py:46`, controller line 92). No validation shipped — invalid parent types silently accepted. PATCH reparent NOT shipped.

### BE-14-14: Amend list endpoint for ancestor filter (EP-09 extension)
- [ ] RED: test `GET /projects/:id/work-items?parent_id=<uuid>` filters to direct children only
- [ ] RED: test `GET /projects/:id/work-items?ancestor_id=<uuid>` returns all descendants
- [ ] RED: test `?ancestor_id=<uuid>&type=story` applies both filters
- [ ] RED: test `?ancestor_id=<non-existent>` returns empty list (no error)
- [ ] GREEN: amend list endpoint filter handling in `WorkItemService.list_work_items` and repository
  - [x] **Partial (parent filter only):** `GET /api/v1/work-items?parent_work_item_id=<uuid>` returns direct children (`backend/app/presentation/controllers/work_item_controller.py:406,444-445`). Query param is `parent_work_item_id`, not `parent_id` as the plan text suggests. `ancestor_id` filter NOT shipped (requires `materialized_path` column).

---

## Group 10: Event Handlers (Celery)

### BE-14-15: Implement rollup cache invalidation Celery task
- [ ] RED: test handler receives `work_item.state_changed` event and calls `CompletionRollupService.invalidate` with correct args
- [ ] RED: test handler receives `work_item.parent_changed` event and invalidates both old and new parent chains
- [ ] RED: test handler receives `work_item.created` (with parent) and invalidates parent chain
- [ ] RED: test handler receives work item deleted event and invalidates former parent chain
- [ ] RED: test handler is idempotent (double-delivery does not error)
- [ ] GREEN: implement `infrastructure/events/handlers/rollup_invalidation_handler.py`
- Acceptance: Celery task is `@shared_task` with `bind=True`; errors are logged and re-raised (let Celery retry)

---

## Completion Checklist

- [ ] All migrations applied and tested on clean + populated DB
- [ ] `mypy --strict` passes with no new errors
- [ ] All unit tests run without real DB or Redis (fakes only)
- [ ] Integration tests use test DB (not production)
- [ ] Workspace scoping verified in every service method and repository query
- [ ] No N+1 queries (EXPLAIN verified on key endpoints)
- [ ] Security: all endpoints require Bearer JWT; workspace scoping enforced in service layer (not just controller)

---

## Reconciliation notes (2026-04-17)

**Opportunistic EP-14 slice — parent link plumbing only, no validators.** Today's pass threaded `parent_work_item_id` through the create path and added a direct-children list filter. The hierarchy algorithms (`HierarchyValidator`, `MaterializedPathService`, cycle detection, `CompletionRollupService`, `TreeQueryService`) remain un-shipped.

Shipped:

- **Migration 0031** — extends `work_items_type_valid` CHECK to include `story`, `milestone`. Uses zero-downtime `ADD CONSTRAINT NOT VALID` + `VALIDATE CONSTRAINT` pattern with downgrade safety (refuses if offending rows exist). Note: the domain enum and ORM `_WORK_ITEM_TYPES` already had `story`/`milestone` — the DB CHECK was out of sync. This fixes the drift.
- **`parent_work_item_id` threaded through the create surface** — `CreateWorkItemCommand`, `WorkItemService.create`, `POST /api/v1/work-items`, `WorkItemCreateRequest`. Persists the FK; no validation.
- **`GET /api/v1/work-items?parent_work_item_id=<uuid>`** — returns direct children. Note: param name is `parent_work_item_id` (plan text suggests `parent_id` — the shipped name matches the column, not the plan).
- **Frontend surface** (listed for context; EP-14 tasks-frontend.md covers it) — `useChildItems(parentId)` + `ChildItemsTab` component; `useParentWorkItem(id)` + parent Link in work-item-header; `useWorkItemTags` (EP-15 integration). See `frontend/hooks/work-item/use-child-items.ts`, `use-parent-work-item.ts`, `use-work-item-tags.ts` + corresponding `frontend/__tests__/hooks/work-item/*.test.ts`.

Gaps intentionally left un-ticked — `materialized_path` column, `HierarchyValidator` (Group 3), `MaterializedPathService` (Group 4), cycle detection (Group 5), reparent/delete hierarchy logic in service (BE-14-08, BE-14-09), `CompletionRollupService` (Group 7), `TreeQueryService` (Group 8), hierarchy endpoints (BE-14-12), rollup Celery handler (Group 10). **>75% of the plan is still pending.** When EP-14 enters formal delivery, the algorithms + `materialized_path` column are the pre-requisites before any validator work can ship.
