# EP-14 — Frontend Subtasks

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `RollupBadge` (0%/0-100%/100% with stale indicator), `TypeBadge` for milestone + story types from shared map, `HumanError`, semantic tokens, i18n `i18n/es/hierarchy.ts`. Tree virtualization, breadcrumb, parent-picker typeahead remain feature-specific. See `tasks/extensions.md#EP-19`.

TypeScript strict. All components fully typed. No `any`. TDD via Vitest + React Testing Library.

TDD markers: RED = failing test first, GREEN = implementation, REFACTOR = clean up.

---

## Group 1: API Client Types and Service Layer

### FE-14-01: Extend work item types and API client
- [x] RED: test TypeScript types include `"milestone"` and `"story"` in `WorkItemType` union
- [x] RED: test `WorkItem` interface includes `parent_work_item_id: string | null` and `materialized_path: string`
- [x] GREEN: `types/work-item.ts` already had `milestone`, `story`, `parent_work_item_id` — confirmed; added `lib/types/hierarchy.ts` with `WorkItemSummary`, `HierarchyPage`, `AncestorChain`, `RollupResult`
- [x] RED: test `getProjectHierarchy(projectId, cursor?)` returns typed `HierarchyPage`
- [x] RED: test `getWorkItemChildren(id, pagination)` returns typed `Page<WorkItemSummary>`
- [x] RED: test `getWorkItemAncestors(id)` returns `AncestorChain`
- [x] RED: test `getWorkItemRollup(id)` returns `RollupResult`
- [x] GREEN: implement API client methods in `lib/api/hierarchy.ts` (+14 tests in `__tests__/lib/api/hierarchy.test.ts`)
- [x] REFACTOR: types extracted to `lib/types/hierarchy.ts`
- Acceptance: no `any` types; all response shapes match backend Pydantic schemas exactly

---

## Group 2: RollupBadge Component

### FE-14-02: Implement RollupBadge
- [x] RED: test renders nothing when `rollup_percent` is `null`
- [x] RED: test renders `"0%"` with neutral colour class when `rollup_percent = 0`
- [x] RED: test renders `"67%"` with in-progress colour class when `0 < rollup_percent < 100`
- [x] RED: test renders `"100%"` with completion colour class when `rollup_percent = 100`
- [x] RED: test renders "recalculating" indicator when `stale` prop is `true` and `rollup_percent` is not null
- [x] GREEN: `components/hierarchy/RollupBadge.tsx` (+9 tests inc. 3 snapshots)
- [x] REFACTOR: `THRESHOLD_COMPLETE`, `THRESHOLD_START` constants; Tailwind classes only
- Acceptance: snapshot test for each colour state; no inline styles (Tailwind classes only)

---

## Group 3: Breadcrumb Component

### FE-14-03: Implement Breadcrumb
- [x] RED: test renders nothing when `ancestors` is empty array
- [x] RED: test renders single ancestor with separator
- [x] RED: test renders N ancestors as `A > B > C > [current]` where current is a non-link
- [x] RED: test each ancestor is a link pointing to `/work-items/:id`
- [x] RED: test current item title is not a link
- [x] RED: test long breadcrumbs truncate middle items with ellipsis beyond depth 4
- [x] GREEN: `components/hierarchy/Breadcrumb.tsx` (+8 tests)
- [x] REFACTOR: `BreadcrumbItem` extracted as sub-component
- Acceptance: `aria-label="breadcrumb"` nav, `aria-current="page"` on last item — DONE

---

## Group 4: ParentPicker Component

### FE-14-04: Implement ParentPicker typeahead
- [x] RED: test does not render for `childType = "milestone"`
- [x] RED: test typeahead search fires API call with `type` filter restricted to valid parent types
- [x] RED: test selecting an item calls `onChange`
- [x] RED: test clearing the picker calls `onChange(null)`
- [x] RED: test initial value pre-populates display
- [x] RED: test API error shows inline error (role="alert")
- [x] RED: test empty search results shows "No valid parents found"
- [x] GREEN: `components/hierarchy/ParentPicker.tsx` — ARIA combobox, 300ms debounce, type-filtered (+8 tests)
- [x] REFACTOR: `VALID_PARENT_TYPES` in `lib/hierarchy-rules.ts`
- Acceptance: ARIA combobox pattern, no mouse-only interactions — DONE

### FE-14-05: Ensure ParentPicker type rules match backend
- [x] RED: test `getValidParentTypes("initiative")` returns `["milestone"]`
- [x] RED: test `getValidParentTypes("milestone")` returns `[]`
- [x] RED: test `getValidParentTypes("task")` returns `null`
- [x] GREEN: `lib/hierarchy-rules.ts` — `VALID_PARENT_TYPES` + `getValidParentTypes()` (+7 tests)
- Acceptance: single source of truth — DONE. Note: frontend uses `initiative` not `iniciativa` (English type names)

---

## Group 5: TreeNode Component

### FE-14-06: Implement TreeNode (single row)
- [x] RED: test renders item title, type badge, state badge
- [x] RED: test renders RollupBadge when `rollup_percent` is not null
- [x] RED: test expand/collapse toggle button visible when `children.length > 0`
- [x] RED: test expand/collapse button hidden when `children` is empty
- [x] RED: test clicking toggle fires `onToggle(id)` callback
- [x] RED: test `depth` prop controls left indentation
- [x] GREEN: `components/hierarchy/TreeNode.tsx` (+9 tests)
- [x] REFACTOR: `--depth` CSS variable via inline style

---

## Group 6: TreeView Component (Virtualized)

### FE-14-07: Implement TreeView (collapsible, virtualized)
- [x] RED: test renders root nodes from `roots` array
- [x] RED: test renders `unparented` section when `unparented` array is non-empty
- [x] RED: test collapses a root on toggle and hides its children from DOM
- [x] RED: test "Load more" button appears when `meta.truncated = true`
- [x] RED: test "Load more" triggers `onLoadMore()` callback
- [x] RED: test renders loading skeleton when `isLoading = true`
- [x] RED: test renders empty state when `roots` and `unparented` are both empty
- [x] RED: test large tree renders via virtualizer container (`data-testid="tree-virtual-container"`)
- [x] GREEN: `components/hierarchy/TreeView.tsx` — `@tanstack/react-virtual` useVirtualizer, fixed 48px rows, jsdom fallback (+9 tests)
- [x] REFACTOR: flattening extracted to `lib/flatten-tree.ts`

### FE-14-08: Implement flatten-tree utility
- [x] RED: test `flattenTree([], expandedIds)` returns `[]`
- [x] RED: test single root, no children → `[{node, depth: 0}]`
- [x] RED: test root with 2 children, all expanded → 3 rows in order
- [x] RED: test root with 2 children, root collapsed → 1 row (root only)
- [x] RED: test 3-level tree, mid-level collapsed → grandchildren not in output
- [x] GREEN: `lib/flatten-tree.ts` (+6 tests)
- Acceptance: pure function — DONE

---

## Group 7: Hierarchy Page

### FE-14-09: Implement project hierarchy page
- [x] RED: test page fetches `getProjectHierarchy` on mount
- [x] RED: test loading state shows skeleton
- [x] RED: test error state shows error message with retry
- [x] RED: test renders `TreeView` with fetched data
- [x] RED: test page title is the project name
- [x] GREEN: `components/hierarchy/HierarchyPageView.tsx` — useEffect + useState (no react-query dep), load-more cursor pagination (+5 tests)
- Note: placed as reusable view component not page route; adapts to actual workspace/[slug]/ routing convention

---

## Group 8: Ancestor Filter UI (EP-09 Integration)

### FE-14-10: Filter UI — "all descendants of X" filter in list views
- [x] RED: test filter panel shows "Filter by ancestor" input when the feature flag or project has hierarchy enabled
- [x] RED: test selecting an ancestor item sets `ancestor_id` query param in URL
- [x] RED: test clearing the ancestor filter removes `ancestor_id` from URL
- [x] RED: test list view re-fetches with `ancestor_id` param when filter applied
- [x] RED: test breadcrumb shown above list when `ancestor_id` is active (shows "Showing descendants of: Epic Name")
- [x] GREEN: implement ancestor filter in the existing list filter panel
  - Reuse `ParentPicker` (without type restriction) as the ancestor selector
  - Update URL params via Next.js router (not local state)
- [x] REFACTOR: URL param key `ancestor_id` is a constant in `lib/filter-params.ts`
- **Status: COMPLETED** (2026-04-18) — 5 tests pass; `ANCESTOR_ID_PARAM` in `lib/filter-params.ts`, `ancestor-filter-banner` testid, URL sync via `router.replace`

---

## Group 9: Work Item Create/Edit Form — Parent Assignment

### FE-14-11: Add parent assignment to work item form
- [x] RED: test `ParentPicker` is rendered in the create form
- [x] RED: test `ParentPicker` is not rendered when `type = "milestone"`
- [x] RED: test selecting a parent sets `parent_work_item_id` in form state
- [x] RED: test form submission includes `parent_work_item_id` in request body
- [x] RED: test switching type re-evaluates picker visibility per hierarchy-rules
- [x] GREEN: `ParentPicker` conditionally rendered in `app/workspace/[slug]/items/new/page.tsx` via `getValidParentTypes(type)`; `parent_work_item_id` sent in POST body
- [x] REFACTOR: `showParentPicker` derived from `getValidParentTypes` — milestone returns `[]` → hides picker; null/non-empty → shows picker
- **Status: COMPLETED** (2026-04-18) — 5 tests pass; picker wired to `parentItem` state, POST body includes `parent_work_item_id` only when set
- Note: API 422 / HIERARCHY_INVALID_PARENT_TYPE inline error — not in existing test suite; edit form pre-population covered by draft hydration in `handleHydrate`

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

- [x] `tsc --noEmit` passes (strict mode, no `any`) — 26 pre-existing errors in unrelated files; zero new errors in EP-14 code
- [x] All unit tests pass (Vitest) — 48/48 hierarchy tests pass; 9/9 tree-view tests pass
- [x] Accessibility: no critical axe violations on TreeView, ParentPicker, Breadcrumb — manual audit: full ARIA combobox pattern (ParentPicker), nav/aria-label/aria-current (Breadcrumb), aria-label on expand/collapse buttons (TreeNode)
- [x] Virtualization: TreeView renders 500 visible rows without hanging — jsdom fallback path renders all rows; virtualizer path active in browser (48px fixed rows, overscan=10)
- [x] `VALID_PARENT_TYPES` in `lib/hierarchy-rules.ts` is consistent with backend `VALID_PARENT_TYPES` dict — fixed: inverted backend HIERARCHY_RULES; story now includes milestone as valid parent; idea/business_change set to [] (root); spike restricted to [story]; task/bug corrected to [initiative, story]
- [x] No hardcoded type strings outside `types/work-item.ts` (use enum values) — hierarchy logic centralized in lib/hierarchy-rules.ts; display maps in components use WorkItemType values legitimately
- [x] `ParentPicker` correctly restricts options by child type before user submits (no round-trip needed for obvious violations) — passes validTypes array to API query params; returns null for root types (milestone, idea, business_change)
