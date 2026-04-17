# EP-14 — Frontend Subtasks

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `RollupBadge` (0%/0-100%/100% with stale indicator), `TypeBadge` for milestone + story types from shared map, `HumanError`, semantic tokens, i18n `i18n/es/hierarchy.ts`. Tree virtualization, breadcrumb, parent-picker typeahead remain feature-specific. See `tasks/extensions.md#EP-19`.

TypeScript strict. All components fully typed. No `any`. TDD via Vitest + React Testing Library.

TDD markers: RED = failing test first, GREEN = implementation, REFACTOR = clean up.

---

## Group 1: API Client Types and Service Layer

### FE-14-01: Extend work item types and API client
- [ ] RED: test TypeScript types include `"milestone"` and `"story"` in `WorkItemType` union
- [ ] RED: test `WorkItem` interface includes `parent_work_item_id: string | null` and `materialized_path: string`
- [ ] GREEN: update `types/work-item.ts` — add `MILESTONE`, `STORY` to enum, add fields to interface
- [ ] RED: test `getProjectHierarchy(projectId, cursor?)` returns typed `HierarchyPage`
- [ ] RED: test `getWorkItemChildren(id, pagination)` returns typed `Page<WorkItemSummary>`
- [ ] RED: test `getWorkItemAncestors(id)` returns `AncestorChain`
- [ ] RED: test `getWorkItemRollup(id)` returns `RollupResult`
- [ ] GREEN: implement API client methods in `services/hierarchy-api.ts`
- [ ] REFACTOR: extract `HierarchyPage`, `AncestorChain`, `RollupResult` as shared types
- Acceptance: no `any` types; all response shapes match backend Pydantic schemas exactly

---

## Group 2: RollupBadge Component

### FE-14-02: Implement RollupBadge
- [ ] RED: test renders nothing when `rollup_percent` is `null`
- [ ] RED: test renders `"0%"` with neutral colour class when `rollup_percent = 0`
- [ ] RED: test renders `"67%"` with in-progress colour class when `0 < rollup_percent < 100`
- [ ] RED: test renders `"100%"` with completion colour class when `rollup_percent = 100`
- [ ] RED: test renders "recalculating" indicator when `stale` prop is `true` and `rollup_percent` is not null
- [ ] GREEN: implement `components/hierarchy/RollupBadge.tsx`
- [ ] REFACTOR: colour thresholds as named constants (not magic numbers)
- Acceptance: snapshot test for each colour state; no inline styles (Tailwind classes only)

---

## Group 3: Breadcrumb Component

### FE-14-03: Implement Breadcrumb
- [ ] RED: test renders nothing when `ancestors` is empty array
- [ ] RED: test renders single ancestor with separator
- [ ] RED: test renders N ancestors as `A > B > C > [current]` where current is a non-link
- [ ] RED: test each ancestor is a link pointing to `/work-items/:id`
- [ ] RED: test current item title is not a link
- [ ] RED: test long breadcrumbs truncate middle items with ellipsis beyond depth 4
- [ ] GREEN: implement `components/hierarchy/Breadcrumb.tsx`
- [ ] REFACTOR: extract `BreadcrumbItem` as sub-component
- Acceptance: accessible — `aria-label="breadcrumb"`, `aria-current="page"` on last item

---

## Group 4: ParentPicker Component

### FE-14-04: Implement ParentPicker typeahead
- [ ] RED: test does not render for `childType = "milestone"` (milestones cannot have parents)
- [ ] RED: test typeahead search fires API call with `type` filter restricted to valid parent types
  - e.g., for `childType = "story"` the query includes `type=epic,initiative`
  - for `childType = "task"` no type filter is applied
- [ ] RED: test selecting an item sets `value` and calls `onChange`
- [ ] RED: test clearing the picker calls `onChange(null)`
- [ ] RED: test initial value (edit mode) pre-populates and displays current parent
- [ ] RED: test API error shows inline error message, does not crash
- [ ] RED: test empty search results shows "No valid parents found" message
- [ ] GREEN: implement `components/hierarchy/ParentPicker.tsx`
  - Typeahead hits `GET /api/v1/projects/:project_id/work-items?q=<query>&type=<valid_types>`
  - Debounce search input (300ms)
  - Renders type badge next to each result option
- [ ] REFACTOR: `VALID_PARENT_TYPES` constant mirrors backend rules — single source of truth in `lib/hierarchy-rules.ts`
- Acceptance: keyboard-accessible (ARIA combobox pattern); no mouse-only interactions

### FE-14-05: Ensure ParentPicker type rules match backend
- [ ] RED: test `getValidParentTypes("story")` returns `["epic", "initiative"]`
- [ ] RED: test `getValidParentTypes("milestone")` returns `[]`
- [ ] RED: test `getValidParentTypes("task")` returns `null` (null = no type restriction)
- [ ] GREEN: implement `lib/hierarchy-rules.ts` with `VALID_PARENT_TYPES` and `getValidParentTypes(childType)`
- Acceptance: this file is the single source of truth for frontend type rules; no inline arrays elsewhere

---

## Group 5: TreeNode Component

### FE-14-06: Implement TreeNode (single row)
- [ ] RED: test renders item title, type badge, state badge
- [ ] RED: test renders RollupBadge when `rollup_percent` is not null
- [ ] RED: test expand/collapse toggle button visible when `children.length > 0`
- [ ] RED: test expand/collapse button hidden when `children` is empty
- [ ] RED: test clicking toggle fires `onToggle(id)` callback
- [ ] RED: test collapsed node does not render children
- [ ] RED: test expanded node renders children recursively
- [ ] RED: test `depth` prop controls left indentation (depth * 24px)
- [ ] GREEN: implement `components/hierarchy/TreeNode.tsx`
- [ ] REFACTOR: indentation as a CSS variable `--depth` set via inline style (avoids Tailwind dynamic class purge)

---

## Group 6: TreeView Component (Virtualized)

### FE-14-07: Implement TreeView (collapsible, virtualized)
- [ ] RED: test renders root nodes from `roots` array
- [ ] RED: test renders `unparented` section when `unparented` array is non-empty
- [ ] RED: test collapses a root on toggle and hides its children from DOM
- [ ] RED: test "Load more" button appears when `meta.truncated = true`
- [ ] RED: test "Load more" triggers `onLoadMore()` callback
- [ ] RED: test renders loading skeleton when `isLoading = true`
- [ ] RED: test renders empty state when `roots` and `unparented` are both empty
- [ ] RED: test large tree (500+ nodes) renders without blocking main thread — virtualization active
  - Use `@tanstack/virtual` `useVirtualizer`; assert only visible rows are in DOM
- [ ] GREEN: implement `components/hierarchy/TreeView.tsx`
  - Flatten tree to a virtualizable row list when expanded state changes
  - `@tanstack/virtual` for the row list; row height is fixed (48px)
- [ ] REFACTOR: extract tree flattening logic to `lib/flatten-tree.ts` (pure function, easily tested)

### FE-14-08: Implement flatten-tree utility
- [ ] RED: test `flattenTree([], expandedIds)` returns `[]`
- [ ] RED: test single root, no children → `[{node, depth: 0}]`
- [ ] RED: test root with 2 children, all expanded → 3 rows in order
- [ ] RED: test root with 2 children, root collapsed → 1 row (root only)
- [ ] RED: test 3-level tree, mid-level collapsed → grandchildren not in output
- [ ] GREEN: implement `lib/flatten-tree.ts`
- Acceptance: pure function; input is `TreeNode[]` + `Set<string>` of expanded IDs; output is `FlatRow[]`

---

## Group 7: Hierarchy Page

### FE-14-09: Implement project hierarchy page
- [ ] RED: test page fetches `getProjectHierarchy` on mount
- [ ] RED: test loading state shows skeleton
- [ ] RED: test error state shows error message with retry
- [ ] RED: test renders `TreeView` with fetched data
- [ ] RED: test page title is the project name
- [ ] GREEN: implement `app/projects/[id]/hierarchy/page.tsx`
  - Use React Query (`useQuery`) for data fetching
  - Pass `cursor` state to `getProjectHierarchy` for pagination
- [ ] REFACTOR: loading/error states as shared `PageShell` pattern

---

## Group 8: Ancestor Filter UI (EP-09 Integration)

### FE-14-10: Filter UI — "all descendants of X" filter in list views
- [ ] RED: test filter panel shows "Filter by ancestor" input when the feature flag or project has hierarchy enabled
- [ ] RED: test selecting an ancestor item sets `ancestor_id` query param in URL
- [ ] RED: test clearing the ancestor filter removes `ancestor_id` from URL
- [ ] RED: test list view re-fetches with `ancestor_id` param when filter applied
- [ ] RED: test breadcrumb shown above list when `ancestor_id` is active (shows "Showing descendants of: Epic Name")
- [ ] GREEN: implement ancestor filter in the existing list filter panel
  - Reuse `ParentPicker` (without type restriction) as the ancestor selector
  - Update URL params via Next.js router (not local state)
- [ ] REFACTOR: URL param key `ancestor_id` is a constant in `lib/filter-params.ts`

---

## Group 9: Work Item Create/Edit Form — Parent Assignment

### FE-14-11: Add parent assignment to work item form
- [ ] RED: test `ParentPicker` is rendered in the create form
- [ ] RED: test `ParentPicker` is not rendered when `type = "milestone"`
- [ ] RED: test selecting a parent sets `parent_work_item_id` in form state
- [ ] RED: test form submission includes `parent_work_item_id` in request body
- [ ] RED: test API 422 with `HIERARCHY_INVALID_PARENT_TYPE` shows inline field error on ParentPicker
- [ ] RED: test edit form pre-populates ParentPicker with current parent when editing
- [ ] GREEN: amend `components/work-items/WorkItemForm.tsx`
- [ ] REFACTOR: ParentPicker is conditionally rendered based on selected type (re-evaluate on type change)

---

## Phase 4: Task Tree Interactions + Dependency Management

> Shipped after Phase 1-3 (commits a2e82d9 TaskTree + cbfccbc ParentBreadcrumb).
> Components `task-tree.tsx`, `task-tree-node.tsx`, `task-tree-add-dialog.tsx`,
> `hooks/work-item/use-task-mutations.ts`, `lib/api/tasks.ts` already live.

### FE-14-P4-01: TaskTreeAddDialog tests
- [x] RED → GREEN: 5 behavioral tests — render, disabled-when-empty, onSuccess POST, parent pre-fill, onCancel
- [x] Commit: `f7270cd` — `__tests__/components/work-item/task-tree-add-dialog.test.tsx` (+5 tests)
- Notes: "Add task" (root) and "Add child" (+) buttons already wired in task-tree.tsx / task-tree-node.tsx

### FE-14-P4-02: DependencyBadge component
- [x] RED: test file `__tests__/components/work-item/dependency-badge.test.tsx` written first (failed — component not found)
- [x] GREEN: `components/work-item/dependency-badge.tsx` — standalone chip, null when no blocks edges, renders →N, tooltip contains blocked titles, ignores relates_to
- [x] REFACTOR: extracted from inline badge in `task-tree-node.tsx`; node now imports DependencyBadge
- [x] Commit: `850e191` — 5 tests, component extracted (+133 lines, -18 inline)

### FE-14-P4-03: DependencyManageDialog (Phase 5)
- [x] RED: 4 tests — renders existing edges, deleteDependency on remove, createDependency on add, onCancel
- [x] GREEN: `components/work-item/dependency-manage-dialog.tsx` — lists outgoing blocks edges with remove, native select for adding new blocks edge
- [x] useTaskMutations extended: `createDependency`, `deleteDependency` added (+2 tests in use-task-mutations.test.ts → 9 total)
- [x] i18n: added 7 new keys to `workspace.itemDetail.tasks.*` in en.json + es.json
- [x] Commit: (pending — this commit)

**Status: COMPLETED** (2026-04-17)
Test delta: +16 tests (22 → 38) across 6 test files.

---

## Deferred Phase: DnD Reparenting

### FE-14-DND-01: DndContext + SortableTree integration
- [x] RED: 8 tests written in `__tests__/components/work-item/task-tree-dnd.test.tsx` — drag handle aria-label, data-drag-id presence, drag handle count, data-testid="drag-handle", cycle error display, aria-disabled when pending, tabIndex=0 on handles
- [x] GREEN: `task-tree.tsx` wrapped in `DndContext` (PointerSensor + KeyboardSensor). `task-tree-node.tsx` uses `useDraggable` + `useDroppable`. `onDragEnd` does optimistic reparent → rollback on error. Client-side cycle guard (isAncestorOf) before API call.
- [x] i18n: added `workspace.itemDetail.tasks.dnd.*` keys to `en.json` + `es.json` (dragHandle, dragging, dragInstructions, cycleError, genericError)
- [x] @dnd-kit/core@6.3.1 + @dnd-kit/sortable@10.0.0 installed
- [x] Commit: `7c62b60` — feat(tasks): dnd-kit drag-and-drop reparent with keyboard access (EP-14)
- Notes: Position-based reorder within same parent deferred (BE has no position PATCH endpoint yet — TODO in commit)

### FE-14-DND-02: Visual polish + error handling
- [x] REFACTOR: removed redundant `isDropTarget` prop from `TaskTreeNode` — each node's own `useDroppable.isOver` handles highlight state
- [x] GripVertical icon (lucide-react) with `data-testid="drag-handle"` per node
- [x] Drop indicator: `data-drop-target="true"` + `bg-primary/10 ring-1 ring-primary/40` on `isOver`
- [x] Cycle error: `CYCLE_DETECTED` from BE (or client-side detect) → `role="alert" aria-live="assertive"` inline error
- [x] `aria-describedby` on row announces drag state to screen readers
- [x] `tsc --noEmit` green, 133 test files / 919 tests all passing
- [x] Commit: `b70b266` — feat(tasks): dnd polish + cycle error handling (EP-14)

**Status: COMPLETED** (2026-04-18)
Test delta (DnD phase): +8 tests (911 → 919 total). Files: 133. Zero regressions.
@dnd-kit/core@6.3.1, @dnd-kit/sortable@10.0.0 (React 18 compat — peer dep satisfied).

---

## Completion Checklist

- [ ] `tsc --noEmit` passes (strict mode, no `any`)
- [ ] All unit tests pass (Vitest)
- [ ] Accessibility: no critical axe violations on TreeView, ParentPicker, Breadcrumb
- [ ] Virtualization: TreeView renders 500 visible rows without hanging (manual test or Lighthouse CI)
- [ ] `VALID_PARENT_TYPES` in `lib/hierarchy-rules.ts` is consistent with backend `VALID_PARENT_TYPES` dict
- [ ] No hardcoded type strings outside `types/work-item.ts` (use enum values)
- [ ] `ParentPicker` correctly restricts options by child type before user submits (no round-trip needed for obvious violations)
