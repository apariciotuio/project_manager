# EP-05 — Implementation Checklist
# Breakdown, Hierarchy & Dependencies

**Status: MVP COMPLETE (2026-04-17)** — full stack shipped: backend phases 1–6 + cross-EP cache-invalidation wiring (`tasks-backend.md` line 47 "**Status: COMPLETED (2026-04-17)**"), and frontend shipped (`components/work-item/task-tree.tsx` + `task-tree-node` + `task-tree-add-dialog` + `hooks/work-item/use-task-tree.ts` + `use-task-mutations.ts` + `lib/api/hierarchy.ts` + `lib/api/tasks.ts`). Tests present in `__tests__/components/work-item/task-tree*.test.tsx` and `__tests__/hooks/work-item/use-task-tree.test.ts`.

The item-level checklist below pre-dates the implementation and was never back-ticked (same pattern as EP-04). Canonical state is `tasks-backend.md` + the code.

v2 carveouts (see `v2-carveout.md`): `TaskService.update_section_links()` service + controller, `GET /work-items/{id}/sections/{section_id}/tasks` controller — both intentionally scope-excluded per the original plan.

Progress tracking: mark `[x]` with a brief note immediately after completing each step.
Phase complete → add `**Status: COMPLETED** (YYYY-MM-DD)`.

---

## Phase 1 — Data Model & Migrations

- [ ] 1.1 Create migration: `task_nodes` table (id, work_item_id, parent_id, title, description, display_order, status, generation_source, materialized_path, created_at/by, updated_at/by)
- [ ] 1.2 Create migration: `task_node_section_links` table (id, task_id, section_id, created_at, UNIQUE constraint)
- [ ] 1.3 Create migration: `task_dependencies` table (id, task_id, depends_on_id, created_at/by, UNIQUE + CHECK self-reference constraint)
- [ ] 1.4 Create all indexes defined in design.md §1 (work_item_id, parent_id, materialized_path gin, section links, dependency edges)
- [ ] 1.5 [RED] Write migration tests: verify constraints reject self-dependency, duplicate link, cascade deletes propagate correctly
- [ ] 1.6 [GREEN] Run migrations, confirm tests pass

---

## Phase 2 — Domain Layer

- [ ] 2.1 [RED] Write unit tests for `TaskNode` entity: status FSM (valid and invalid transitions), construction invariants
- [ ] 2.2 [GREEN] Implement `domain/models/task_node.py` — `TaskNode` entity with `can_transition_to(status)` method
- [ ] 2.3 [RED] Write unit tests for `TaskNodeDraft` value object: LLM response parsing, missing fields, section_type fallback
- [ ] 2.4 [GREEN] Implement `domain/models/task_node_draft.py`
- [ ] 2.5 Define `domain/repositories/task_node_repository.py` interface (get, get_by_work_item, count_by_work_item, create, update, delete, get_tree_flat)
- [ ] 2.6 Define `domain/repositories/task_dependency_repository.py` interface (get_by_work_item, create, delete, get_predecessors, get_successors)

---

## Phase 3 — Cycle Detection (Pure Domain Logic)

- [ ] 3.1 [RED] Write unit tests for cycle detection function: linear chain (no cycle), triangle cycle, self-dependency shortcut, empty graph, single node
- [ ] 3.2 [RED] Write unit tests for cycle path return: verify the path list is correct for caught cycles
- [ ] 3.3 [GREEN] Implement `domain/dependencies/cycle_detector.py` — `has_cycle_after_add(edges, new_edge) -> (bool, list[UUID])` — pure function, no I/O
- [ ] 3.4 [REFACTOR] Ensure function handles large edge lists without recursion depth issues (iterative DFS fallback if needed)

---

## Phase 4 — Infrastructure Layer

- [ ] 4.1 [RED] Write repository tests for `TaskNodeRepositoryImpl`: create, get, get_by_work_item, get flat for recursive CTE, delete cascade
- [ ] 4.2 [GREEN] Implement `infrastructure/persistence/task_node_repository_impl.py` using async SQLAlchemy
- [ ] 4.3 [RED] Write tests for recursive CTE tree query: verify correct nesting, ordering, depth limit at 10
- [ ] 4.4 [GREEN] Implement recursive CTE in `task_node_repository_impl.py` — `get_tree_flat(work_item_id)` returns flat list with depth metadata; service assembles tree
- [ ] 4.5 [RED] Write repository tests for `TaskDependencyRepositoryImpl`: create, delete, get predecessors/successors, load full graph for cycle detection
- [ ] 4.6 [GREEN] Implement `infrastructure/persistence/task_dependency_repository_impl.py`
- [ ] 4.7 [RED] Write repository tests for `TaskSectionLinkRepositoryImpl`: create links, get by task, get by section, delete on cascade
- [ ] 4.8 [GREEN] Implement `infrastructure/persistence/task_section_link_repository_impl.py`
- [ ] 4.9 [RED] Write unit tests for `BreakdownAdapter`: valid LLM JSON response, malformed response, missing section_type, empty tasks list
- [ ] 4.10 [GREEN] Implement `infrastructure/llm/adapters/breakdown_adapter.py` wrapping LLM client (reuse EP-03/EP-04 client)
- [ ] 4.11 Implement `infrastructure/llm/prompts/breakdown_generation.py` — versioned prompt template constant

---

## Phase 5 — Application Services

### TaskService (US-050, US-051, US-052)

- [ ] 5.1 [RED] Write service tests for `generate`: happy path, spec empty → 422, already exists → 409, force=True replaces, LLM failure → rollback
- [ ] 5.2 [GREEN] Implement `TaskService.generate(work_item_id, force)`
- [ ] 5.3 [RED] Write service tests for `create`: manual task with and without section_ids, section_id not belonging to work item → 422
- [ ] 5.4 [GREEN] Implement `TaskService.create(work_item_id, parent_id, title, description, section_ids)`
- [ ] 5.5 [RED] Write service tests for `update`: rename, update description, invalid status transition → 422, transition blocked by predecessors → 422
- [ ] 5.6 [GREEN] Implement `TaskService.update(task_id, **fields)` with FSM guard
- [ ] 5.7 [RED] Write service tests for `reorder`: valid reorder, IDs belonging to different parents → 422, IDs not belonging to work item → 422
- [ ] 5.8 [GREEN] Implement `TaskService.reorder(work_item_id, ordered_ids)`
- [ ] 5.9 [RED] Write service tests for `split`: happy path (both nodes inherit section links), original deleted, siblings shifted, missing title → 422
- [ ] 5.10 [GREEN] Implement `TaskService.split(task_id, title_a, description_a, title_b, description_b)`
- [ ] 5.11 [RED] Write service tests for `merge`: happy path (deduped section links), cross-parent → 422, single source ID → 422, sibling reordering after delete
- [ ] 5.12 [GREEN] Implement `TaskService.merge(source_ids, title, description)`
- [ ] 5.13 [RED] Write service tests for `update_section_links`: valid replacement, invalid section_id → 422
- [ ] 5.14 [GREEN] Implement `TaskService.update_section_links(task_id, section_ids)`
- [ ] 5.15 [RED] Write service tests for completeness cache invalidation: verify `CompletenessCache.invalidate()` called after create and delete
- [ ] 5.16 [GREEN] Wire cache invalidation calls in `TaskService.create()` and `TaskService.delete()`

### DependencyService (US-053)

- [ ] 5.17 [RED] Write service tests for `add_dependency`: happy path, cycle → 422 with path, self → 422, cross-work-item → 422, duplicate → 409
- [ ] 5.18 [GREEN] Implement `DependencyService.add_dependency(task_id, depends_on_id)` — calls cycle detector, then inserts
- [ ] 5.19 [RED] Write service tests for `remove_dependency`: exists → 204, not found → 404
- [ ] 5.20 [GREEN] Implement `DependencyService.remove_dependency(task_id, depends_on_id)`
- [ ] 5.21 [RED] Write service tests for `get_blocked_tasks`: no blocked tasks, one predecessor not done, all predecessors done → not blocked
- [ ] 5.22 [GREEN] Implement `DependencyService.get_blocked_tasks(work_item_id)`

### TaskTreeService (US-054)

- [ ] 5.23 [RED] Write service tests for tree assembly: empty tree, flat list, nested nodes, depth cap respected, is_blocked flag computed correctly
- [ ] 5.24 [GREEN] Implement `TaskTreeService.get_tree(work_item_id)` — fetch flat CTE result, assemble nested dict, inject is_blocked and section_links
- [ ] 5.25 [RED] Write service tests for single node with breadcrumb path: root (empty path), depth-2 node (one ancestor), depth-3 node (two ancestors)
- [ ] 5.26 [GREEN] Implement breadcrumb path computation using `materialized_path` column (no extra DB query)

---

## Phase 6 — Presentation Layer

- [ ] 6.1 [RED] Write controller tests for POST /tasks/generate: 201 success, 409 exists, 422 empty spec, 502 LLM failure
- [ ] 6.2 [GREEN] Implement `task_controller.py` generate endpoint
- [ ] 6.3 [RED] Write controller tests for CRUD endpoints (create, update, delete, get single)
- [ ] 6.4 [GREEN] Implement CRUD endpoints in `task_controller.py`
- [ ] 6.5 [RED] Write controller tests for split and merge endpoints: happy paths + all error shapes
- [ ] 6.6 [GREEN] Implement split and merge endpoints
- [ ] 6.7 [RED] Write controller tests for reorder endpoint
- [ ] 6.8 [GREEN] Implement reorder endpoint
- [ ] 6.9 [RED] Write controller tests for section-links PATCH endpoint
- [ ] 6.10 [GREEN] Implement section-links endpoint
- [ ] 6.11 [RED] Write controller tests for dependency endpoints: add (cycle error shape), remove, list, blocked list
- [ ] 6.12 [GREEN] Implement `task_dependency_controller.py`
- [ ] 6.13 [RED] Write controller tests for GET /task-tree: full tree shape, empty tree, is_blocked flags, depth truncation flag
- [ ] 6.14 [GREEN] Implement `task_tree_controller.py`
- [ ] 6.15 [RED] Write controller tests for GET /sections/:sid/tasks
- [ ] 6.16 [GREEN] Implement section-to-tasks lookup endpoint

---

## Phase 7 — EP-04 Completeness Integration

- [ ] 7.1 [RED] Write unit tests for `check_breakdown` dimension checker: 0 tasks → filled=False, 1+ tasks → filled=True
- [ ] 7.2 [GREEN] Implement `check_breakdown` in `domain/quality/dimension_checkers.py`
- [ ] 7.3 [RED] Write service test: `CompletenessService.compute()` injects `task_count` from `TaskNodeRepository.count_by_work_item()`
- [ ] 7.4 [GREEN] Update `CompletenessService` to inject task_count and pass to `check_breakdown`
- [ ] 7.5 Verify `task_count` query is covered by existing `idx_task_nodes_work_item_id` index (no new index needed)

---

## Phase 8 — Integration Tests

- [ ] 8.1 End-to-end: generate → view tree → split task → view tree (verify structure)
- [ ] 8.2 End-to-end: generate → add dependency → attempt cycle → verify rejection
- [ ] 8.3 End-to-end: merge two tasks → verify deduped section links → view tree
- [ ] 8.4 End-to-end: task status transition blocked by predecessor → verify 422
- [ ] 8.5 End-to-end: completeness score changes when task nodes created (breakdown dimension flips)

---

## Phase 9 — Review Gates

- [ ] 9.1 Run `code-reviewer` agent on all EP-05 changes
- [ ] 9.2 Run `review-before-push` workflow
- [ ] 9.3 Address all Must Fix findings before merge
