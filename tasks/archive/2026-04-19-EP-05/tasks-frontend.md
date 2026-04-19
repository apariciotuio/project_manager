# EP-05 Frontend Tasks — Breakdown, Hierarchy & Dependencies

**Status: MVP COMPLETE** — shipped per the following surface:
- Components: `frontend/components/work-item/task-tree.tsx`, `task-tree-node.tsx`, `task-tree-add-dialog.tsx`, `tasks-tab.tsx`
- Hooks: `frontend/hooks/work-item/use-task-tree.ts`, `use-task-mutations.ts`
- API clients: `frontend/lib/api/hierarchy.ts`, `lib/api/tasks.ts`
- Tests: `frontend/__tests__/components/work-item/task-tree*.test.tsx`, `__tests__/hooks/work-item/use-task-tree.test.ts`

The item-level checklist below pre-dates the implementation and was never back-ticked. Canonical state is the shipped code + tests.

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopts `StateBadge`, `SeverityBadge`, `HumanError`, semantic tokens, i18n. Tree virtualization, drag-to-reorder, split/merge dialogs are feature-specific.

Tech stack: Next.js 14+ App Router, TypeScript strict, Tailwind CSS

Blocked by: All backend API endpoints for EP-05 must exist and be accessible. EP-19 catalog available. ✓ satisfied.

---

## API Client Contract

All requests require `Authorization: Bearer <token>` header.

```typescript
// src/lib/api/tasks.ts

export type TaskStatus = 'draft' | 'in_progress' | 'done';
export type GenerationSource = 'llm' | 'manual';

export interface SectionLink {
  section_id: string;
  section_type: string;
}

export interface TaskNode {
  id: string;
  work_item_id: string;
  parent_id: string | null;
  title: string;
  description: string;
  display_order: number;
  status: TaskStatus;
  generation_source: GenerationSource;
  materialized_path: string;
  section_links: SectionLink[];
  is_blocked: boolean;
  blocked_by: string[];
  created_at: string;
  updated_at: string;
}

export interface TaskTreeNode extends Omit<TaskNode, 'children'> {
  children: TaskTreeNode[];
  breadcrumb: string[];
}

export interface TaskTree {
  work_item_id: string;
  nodes: TaskTreeNode[];
}

export interface DependencyGraph {
  predecessors: Pick<TaskNode, 'id' | 'title' | 'status'>[];
  successors: Pick<TaskNode, 'id' | 'title' | 'status'>[];
}

// generateTasks: POST /api/v1/work-items/:id/tasks/generate
// getTaskTree: GET /api/v1/work-items/:id/task-tree
// createTask: POST /api/v1/work-items/:id/tasks
// getTask: GET /api/v1/tasks/:task_id
// updateTask: PATCH /api/v1/tasks/:task_id
// deleteTask: DELETE /api/v1/tasks/:task_id
// reorderTasks: PATCH /api/v1/work-items/:id/tasks/reorder
// splitTask: POST /api/v1/tasks/:task_id/split
// mergeTasks: POST /api/v1/tasks/merge
// updateSectionLinks: PATCH /api/v1/tasks/:task_id/section-links
// addDependency: POST /api/v1/tasks/:task_id/dependencies
// removeDependency: DELETE /api/v1/tasks/:task_id/dependencies/:dep_id
// getDependencies: GET /api/v1/tasks/:task_id/dependencies
// getBlockedTasks: GET /api/v1/work-items/:id/tasks/blocked
```

---

## Group 1 — API Client Layer

### Acceptance Criteria

WHEN `generateTasks(workItemId, { force: false })` is called and server returns 409
THEN the error is typed as `{ code: 'BREAKDOWN_EXISTS' }` (not a generic Error)

WHEN server returns 422 with `SPECIFICATION_EMPTY`
THEN the error is typed as `{ code: 'SPEC_EMPTY' }`

WHEN `addDependency` receives a 422 with `cycle_path`
THEN the error shape is `{ code: 'DEPENDENCY_CYCLE_DETECTED', details: { cycle_path: string[] } }`

WHEN any API call returns 401
THEN the shared auth error handler triggers session refresh; the original call is not silently swallowed

Blocked by: backend Phase 6 complete

- [ ] 1.1 [RED] Write API client tests: `generateTasks` maps 201→success, 409→`BREAKDOWN_EXISTS` error, 422→`SPEC_EMPTY` error
- [ ] 1.2 [RED] Write API client tests: `getTaskTree` returns `TaskTree` shape; `createTask`, `updateTask`, `deleteTask`, `reorderTasks` each tested
- [ ] 1.3 [RED] Write API client tests: `splitTask`, `mergeTasks`, `updateSectionLinks` tested
- [ ] 1.4 [RED] Write API client tests: `addDependency` maps cycle error shape `{ cycle_path: string[] }`; `removeDependency`, `getDependencies`, `getBlockedTasks` tested
- [ ] 1.5 [GREEN] Implement `src/lib/api/tasks.ts` — all functions above with proper TypeScript types and error discrimination
- [ ] 1.6 [REFACTOR] Extract shared error type `ApiError<T extends string>` with `code` + `details` discriminated union

---

## Group 2 — Hooks (Data Fetching & State)

### Acceptance Criteria

WHEN `useTaskTree` returns data
THEN `tree.nodes` is a nested array; root nodes have `parent_id = null`

WHEN `updateTask` is called optimistically and the server rejects with 422 `INVALID_STATUS_TRANSITION`
THEN the optimistic state is reverted and `error` contains `{ code, details.blocked_by }`

WHEN `useGenerateTasks` succeeds
THEN the `useTaskTree` SWR/Query cache for that `workItemId` is invalidated (not just refetched)

WHEN `splitTask` or `mergeTasks` succeed
THEN `useTaskTree` cache is invalidated; subsequent render shows updated tree

WHEN `addDependency` returns a cycle error
THEN `useTaskDependencies` exposes `cycleError: { cycle_path: string[] }` as a distinct field, not the generic `error`

Blocked by: Group 1 complete

- [ ] 2.1 [RED] Test `useTaskTree(workItemId)`: fetches tree, returns `{ tree, isLoading, error, refetch }`; optimistic update on node status change
- [ ] 2.2 [GREEN] Implement `src/hooks/useTaskTree.ts` using SWR or React Query
- [ ] 2.3 [RED] Test `useGenerateTasks(workItemId)`: calls `generateTasks`, invalidates task tree cache on success
- [ ] 2.4 [GREEN] Implement `src/hooks/useGenerateTasks.ts`
- [ ] 2.5 [RED] Test `useTaskMutations(taskId)`: `updateTask`, `deleteTask`, `splitTask` each invalidate `useTaskTree`; optimistic status update on `updateTask`
- [ ] 2.6 [GREEN] Implement `src/hooks/useTaskMutations.ts`
- [ ] 2.7 [RED] Test `useMergeTasks()`: calls `mergeTasks`, invalidates tree on success
- [ ] 2.8 [GREEN] Implement `src/hooks/useMergeTasks.ts`
- [ ] 2.9 [RED] Test `useTaskDependencies(taskId)`: fetches predecessors and successors; `addDependency` shows cycle error inline
- [ ] 2.10 [GREEN] Implement `src/hooks/useTaskDependencies.ts`

---

## Group 3 — Task Tree Component

### Acceptance Criteria

**TaskTreeNode**

WHEN `node.is_blocked = true`
THEN an orange "Blocked" indicator is rendered alongside the title (not just a tooltip)

WHEN `node.children` is non-empty
THEN children are rendered recursively indented; `depth` prop increments by 1 per level

WHEN `readOnly = true`
THEN action menu (split/merge/delete) is hidden; status dropdown is disabled

**TaskTree**

WHEN `useTaskTree` is loading
THEN skeleton placeholder renders (3-level deep placeholders visible)

WHEN tree data is empty and spec is present
THEN "Generate tasks" CTA is rendered (not an error state)

WHEN drag ends on a node and it is dropped within its current parent level
THEN `reorderTasks` is called with the new `ordered_ids` reflecting the post-drop sequence
AND optimistic reorder is reflected in UI before server response

WHEN merge mode is active and exactly 2 nodes are selected
THEN "Merge" button is enabled; selecting a 3rd node replaces the earliest selection (rolling 2-node window or shows an error — spec: enabled only for exactly 2)

Blocked by: Group 2 complete

### TaskTreeNode component

Props interface:
```typescript
interface TaskTreeNodeProps {
  node: TaskTreeNode;
  depth: number;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onStatusChange: (id: string, status: TaskStatus) => void;
  onDelete: (id: string) => void;
  onSplit: (id: string) => void;
  onMergeToggle: (id: string) => void;
  isMergeSelected: boolean;
  readOnly?: boolean;
}
```

- [ ] 3.1 [RED] Write component test: renders title, status badge, action menu; `is_blocked=true` renders blocked indicator; `children` renders recursively
- [ ] 3.2 [GREEN] Implement `src/components/tasks/TaskTreeNode.tsx`
- [ ] 3.3 [RED] Write component test: status badge colors — `draft=gray`, `in_progress=blue`, `done=green`; blocked badge `orange`
- [ ] 3.4 [GREEN] Implement `src/components/tasks/TaskStatusBadge.tsx`

### TaskTree component

Props interface:
```typescript
interface TaskTreeProps {
  workItemId: string;
  readOnly?: boolean;
}
```

- [ ] 3.5 [RED] Write component test: renders full tree from `useTaskTree`; loading state renders skeleton; empty state renders "No tasks yet" with generate button; error state renders retry
- [ ] 3.6 [GREEN] Implement `src/components/tasks/TaskTree.tsx` — recursive render, drag-to-reorder using native drag events (no heavy DnD library) ⚠️ originally MVP-scoped — see decisions_pending.md
- [ ] 3.7 [RED] Write component test: reorder fires `reorderTasks` with correct `ordered_ids` after drag-drop; optimistic reorder reflected immediately
- [ ] 3.8 [GREEN] Implement drag-to-reorder within `TaskTree.tsx`
- [ ] 3.9 [RED] Write component test: merge mode — selecting two nodes enables merge button; clicking merge opens `MergeTaskDialog`
- [ ] 3.10 [GREEN] Implement merge selection mode in `TaskTree.tsx`

---

## Group 4 — Task Form & Dialogs

### Acceptance Criteria

**CreateTaskForm**

WHEN `title` is empty and user clicks submit
THEN form is invalid; submit button remains disabled; inline error "Title is required" shown

WHEN `section_ids` is omitted
THEN task is created with `section_links: []`; no validation error

**EditTaskForm**

WHEN `node.status = 'in_progress'`
THEN status dropdown shows only `in_progress` and `done` (not `draft`)

WHEN `node.is_blocked = true` and user attempts to select `done`
THEN tooltip text reads "Blocked by X predecessors" where X = count from `blocked_by`
AND selecting `done` is allowed in the form but the PATCH returns 422 which is shown inline

**SplitTaskDialog**

WHEN both title fields are filled and user submits
THEN `splitTask` is called; on success, dialog closes and `onSuccess(a, b)` is called with both new nodes

WHEN server returns 422 (e.g., missing fields server-side validation)
THEN error is shown inline inside the dialog (not as a toast)

**MergeTaskDialog**

WHEN `sourceTasks.length < 2`
THEN submit button is disabled (defensive UI — cannot open with < 2 tasks, but guard anyway)

**GenerateTasksButton**

WHEN server returns 409 `BREAKDOWN_EXISTS`
THEN confirmation prompt appears: "Tasks already exist. Regenerate and overwrite?" with Confirm/Cancel buttons

WHEN user confirms, `generateTasks(workItemId, { force: true })` is called
THEN on success, tree cache is invalidated; button returns to default state

WHEN server returns 422 `SPECIFICATION_EMPTY`
THEN inline message shown: "Add spec content first"
AND no confirmation prompt shown

Blocked by: Group 2 complete

### CreateTaskForm

Props:
```typescript
interface CreateTaskFormProps {
  workItemId: string;
  parentId?: string;
  sectionOptions: SectionLink[];
  onSuccess: (node: TaskNode) => void;
  onCancel: () => void;
}
```

- [ ] 4.1 [RED] Test: title required (form invalid if empty), description optional, section_ids multi-select, submit calls `createTask`; success calls `onSuccess`
- [ ] 4.2 [GREEN] Implement `src/components/tasks/CreateTaskForm.tsx` with react-hook-form + zod

### EditTaskForm

- [ ] 4.3 [RED] Test: pre-fills title/description from node; status dropdown only shows valid transitions from current status; blocked status transitions show tooltip "Blocked by X predecessors"; submit calls `updateTask`
- [ ] 4.4 [GREEN] Implement `src/components/tasks/EditTaskForm.tsx`

### SplitTaskDialog

Props:
```typescript
interface SplitTaskDialogProps {
  task: TaskNode;
  open: boolean;
  onSuccess: (a: TaskNode, b: TaskNode) => void;
  onClose: () => void;
}
```

- [ ] 4.5 [RED] Test: two title+description fields; both required; submit calls `splitTask`; on success closes dialog and calls `onSuccess`; API error shown inline
- [ ] 4.6 [GREEN] Implement `src/components/tasks/SplitTaskDialog.tsx`

### MergeTaskDialog

Props:
```typescript
interface MergeTaskDialogProps {
  sourceTasks: TaskNode[];
  open: boolean;
  onSuccess: (merged: TaskNode) => void;
  onClose: () => void;
}
```

- [ ] 4.7 [RED] Test: shows source task titles as chips; title/description fields required; submit calls `mergeTasks`; success closes and calls `onSuccess`
- [ ] 4.8 [GREEN] Implement `src/components/tasks/MergeTaskDialog.tsx`

### GenerateTasksButton

- [ ] 4.9 [RED] Test: shows loading state during generation; 409 shows "Tasks already exist — regenerate?" confirmation; 422 shows "Add spec content first" message; success triggers tree refetch
- [ ] 4.10 [GREEN] Implement `src/components/tasks/GenerateTasksButton.tsx`

---

## Group 5 — Task Detail Panel

### Acceptance Criteria

**TaskDetailPanel**

WHEN `taskId` is provided
THEN panel shows title, description, status badge, section links (each as a chip with `section_type`), breadcrumb trail from `breadcrumb[]`, and DependenciesPanel

WHEN delete is initiated
THEN a confirmation dialog appears before calling `deleteTask`

WHEN delete succeeds
THEN panel closes and tree cache is invalidated

**DependenciesPanel**

WHEN `addDependency` is submitted and returns `DEPENDENCY_CYCLE_DETECTED`
THEN inline error renders: "Dependency would create a cycle: A → B → A" using `cycle_path` IDs resolved to task titles
AND the input is not cleared (user can correct the input)

WHEN `removeDependency` is called
THEN predecessor/successor list is optimistically updated before server confirms

Blocked by: Group 3 and Group 4 complete

### TaskDetailPanel

Props:
```typescript
interface TaskDetailPanelProps {
  taskId: string;
  workItemId: string;
  onClose: () => void;
}
```

- [ ] 5.1 [RED] Test: renders title, description, status, section links, breadcrumb, dependencies panel; edit mode toggle; delete confirmation
- [ ] 5.2 [GREEN] Implement `src/components/tasks/TaskDetailPanel.tsx`

### DependenciesPanel

Props:
```typescript
interface DependenciesPanelProps {
  taskId: string;
  workItemId: string;
}
```

- [ ] 5.3 [RED] Test: renders predecessors and successors lists; add dependency uses `TaskPickerCombobox` (typeahead, never UUID paste); cycle error shows inline message with cycle path (e.g. "A → B → A"); remove dependency button calls `removeDependency`
- [ ] 5.4 [GREEN] Implement `src/components/tasks/DependenciesPanel.tsx` — add-dependency input is `TaskPickerCombobox`, not a free-text UUID field
  - Acceptance criteria: WHEN adding a dependency THEN user searches by task title, selects from autocomplete, never pastes UUIDs
- [ ] 5.5 [RED] Test: cycle error message clearly shows the cycle path as a readable chain of task titles (not raw UUIDs)
- [ ] 5.6 [GREEN] Implement cycle path rendering in `DependenciesPanel`

### TaskPickerCombobox

Component: `src/components/tasks/TaskPickerCombobox.tsx`

Props:
```typescript
interface TaskPickerComboboxProps {
  workItemId: string;
  excludeTaskId: string;  // exclude the task being edited from results
  onSelect: (task: Pick<TaskNode, 'id' | 'title'>) => void;
  placeholder?: string;
}
```

- [ ] 5.7 [RED] Test: typing ≥2 chars debounces 300ms then calls `searchTasks(workItemId, query)`; results render as title + ID chip; selecting a result calls `onSelect`; empty results show "No tasks found"; excluded task ID never appears in results
- [ ] 5.8 [GREEN] Implement `src/components/tasks/TaskPickerCombobox.tsx`
- [ ] Add API client function: `searchTasks(workItemId: string, q: string): Promise<Pick<TaskNode, 'id' | 'title'>[]>` → `GET /api/v1/work-items/:id/tasks/search?q=<text>` (top 10 by title match)

---

## Group 6 — Page Integration

Blocked by: Groups 3–5 complete

### Work Item Detail page (extend existing EP-01/EP-04 page)

- [ ] 6.1 [RED] Test: work item detail page includes `TaskTree` component in a "Breakdown" tab or section; `readOnly` prop passed when user lacks editor role
- [ ] 6.2 [GREEN] Add `TaskTree` to the work item detail page at `src/app/(workspace)/items/[id]/breakdown/page.tsx` (or extend existing tab layout)
- [ ] 6.3 [RED] Test: clicking a task node opens `TaskDetailPanel` as a slide-over panel
- [ ] 6.4 [GREEN] Wire `TaskDetailPanel` slide-over to `TaskTree` node selection
- [ ] 6.5 [RED] Test: blocked tasks section at bottom of breakdown page; blocked count shown in section header
- [ ] 6.6 [GREEN] Implement blocked tasks section using `getBlockedTasks` hook

---

## Group 7 — Responsive Behavior & States

- [ ] 7.1 Mobile breakpoint: tree collapses to flat list sorted by `display_order`; drag-to-reorder disabled on touch; tap opens `TaskDetailPanel` full-screen
- [ ] 7.2 [RED] Test: loading skeleton renders correct number of placeholder nodes (3 levels deep)
- [ ] 7.3 [GREEN] Implement `TaskTreeSkeleton` component
- [ ] 7.4 [RED] Test: empty state — no tasks, spec present → shows "Generate tasks" CTA; no tasks, spec absent → shows "Add spec content first" message
- [ ] 7.5 [GREEN] Implement empty states in `TaskTree.tsx`
- [ ] 7.6 [RED] Test: error state in tree shows retry button; retry calls `refetch`
- [ ] 7.7 [GREEN] Implement error boundary / error state in `TaskTree.tsx`
