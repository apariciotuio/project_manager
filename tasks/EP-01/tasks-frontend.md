# EP-01 Frontend Tasks — Work Item Lifecycle & State Machine

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `StateBadge` (replaces local `StateChip`/`DerivedStateBadge`), `TypeBadge`, `TypedConfirmDialog` (replaces local force-ready modal; min-char logic moves out of UI into business validation), `HumanError`, semantic tokens, i18n `i18n/es/workitem.ts`. See `tasks/extensions.md#EP-19`.

Branch: `feature/ep-01-frontend`
Refs: EP-01
Depends on: EP-00 frontend (AuthProvider, API client), EP-01 backend API, EP-19 catalog

---

## API Contract (Blocked by: EP-01 backend)

All endpoints require `access_token` cookie (set by EP-00).

**WorkItem response shape:**
```typescript
interface WorkItemResponse {
  id: string
  title: string
  type: WorkItemType
  state: WorkItemState
  derived_state: DerivedState | null
  owner_id: string
  creator_id: string
  project_id: string
  description: string | null
  priority: Priority | null
  due_date: string | null  // ISO 8601 date
  tags: string[]
  completeness_score: number  // 0–100
  has_override: boolean
  override_justification: string | null
  owner_suspended_flag: boolean
  created_at: string
  updated_at: string
  deleted_at: string | null
}
```

**Transition request:** `{ target_state: WorkItemState, reason?: string }`
**Force-ready request:** `{ justification: string, confirmed: true }`
**Reassign request:** `{ new_owner_id: string }`

**Error shape:** `{ error: { code: string, message: string, details?: object } }`

---

## Phase 1 — Type Definitions

- [ ] Implement `src/types/work-item.ts`:
  - `WorkItemState` enum: `draft | in_clarification | in_review | changes_requested | partially_validated | ready | exported`
  - `WorkItemType` enum: `idea | bug | enhancement | task | initiative | spike | business_change | requirement`
  - `DerivedState` enum: `in_progress | blocked | ready`
  - `WorkItemResponse` interface (full response shape above)
  - `WorkItemCreateRequest`, `WorkItemUpdateRequest`, `TransitionRequest`, `ForceReadyRequest`, `ReassignOwnerRequest`
  - `PagedWorkItemResponse<T>`: `{ items: T[], total: number, page: number, page_size: number }`
  - `StateTransitionRecord`, `OwnershipRecord` for audit trail responses

---

## Phase 2 — API Client Functions

File: `src/lib/api/work-items.ts`

- [ ] Implement `createWorkItem(data: WorkItemCreateRequest): Promise<WorkItemResponse>`
- [ ] Implement `getWorkItem(id: string): Promise<WorkItemResponse>`
- [ ] Implement `listWorkItems(projectId: string, filters: WorkItemFilters): Promise<PagedWorkItemResponse<WorkItemResponse>>`
- [ ] Implement `updateWorkItem(id: string, data: WorkItemUpdateRequest): Promise<WorkItemResponse>`
- [ ] Implement `deleteWorkItem(id: string): Promise<void>`
- [ ] Implement `transitionState(id: string, data: TransitionRequest): Promise<WorkItemResponse>`
- [ ] Implement `forceReady(id: string, data: ForceReadyRequest): Promise<WorkItemResponse>`
- [ ] Implement `reassignOwner(id: string, data: ReassignOwnerRequest): Promise<WorkItemResponse>`
- [ ] Implement `getTransitions(id: string): Promise<StateTransitionRecord[]>`
- [ ] Implement `getOwnershipHistory(id: string): Promise<OwnershipRecord[]>`
- [ ] [RED] Write unit tests for each function using MSW handlers: happy path returns typed response, 404 resolves to thrown error with `code`, 422 resolves to thrown error with `details`

### Acceptance Criteria — Phase 2

WHEN `createWorkItem({ title: "Test", type: "bug", project_id: "uuid" })` is called and MSW returns 201
THEN the returned value is typed as `WorkItemResponse` (no `any`)
AND `workItem.state === "draft"`

WHEN `getWorkItem("nonexistent-id")` is called and MSW returns 404
THEN the function throws an error with `error.code === "WORK_ITEM_NOT_FOUND"`
AND does NOT return `null` (throws, does not resolve to null)

WHEN `transitionState(id, { target_state: "in_review" })` is called and MSW returns 422
THEN the function throws an error with `error.details.from_state` and `error.details.to_state` accessible

WHEN `forceReady(id, { justification: "...", confirmed: true })` is called and MSW returns 403
THEN the function throws with `error.code === "NOT_OWNER"`

---

## Phase 3 — Data Fetching Hooks

**Source of truth for work item hooks is EP-01. EP-09 adds only list-specific hooks (`useWorkItemList`) for its paginated listing concerns. Do not redefine `useWorkItem(id)` or core mutation hooks in other epics.**

File: `src/hooks/use-work-item.ts` and `src/hooks/use-work-items.ts`

- [ ] Implement `useWorkItem(id: string)` hook using React Query (or SWR):
  - Returns `{ workItem, isLoading, isError, refetch }`
  - Cache key: `['work-item', id]`
- [ ] Implement `useWorkItems(projectId: string, filters)` hook:
  - Returns `{ workItems, total, isLoading, isError }`
  - Supports pagination: `page`, `page_size` params
- [ ] Implement `useTransitionState()` mutation hook:
  - On success: invalidates `['work-item', id]`, `['work-items', workspace_id]`, `['dashboard', 'global']`, `['inbox', user_id]`, `['completeness', id]` caches
  - Returns `{ transition, isLoading, error }`
- [ ] Implement `useForceReady()` mutation hook
- [ ] Implement `useReassignOwner()` mutation hook
- [ ] [RED] Write hook tests using React Query test utils + MSW: loading state on initial fetch, populated state after successful fetch, error state on API failure, cache invalidation after mutation

### Acceptance Criteria — useTransitionState cache invalidation

WHEN `useTransitionState()` mutation succeeds
THEN `['work-item', id]` is invalidated
AND `['work-items', workspace_id]` (all list queries) is invalidated
AND `['dashboard', 'global']` is invalidated
AND `['inbox', user_id]` is invalidated
AND `['completeness', id]` is invalidated
AND the list view, dashboard, inbox, and completeness score all reflect the new state without a full page reload

---

## Phase 4 — Work Item List Page

Page: `src/app/workspace/[slug]/work-items/page.tsx`

- [ ] [RED] Write page component tests: renders loading skeleton, renders list of work items on load, renders empty state when list is empty, pagination controls work
- [ ] [GREEN] Implement `WorkItemsPage`:
  - Uses `useWorkItems()` for data fetching
  - Renders `WorkItemCard` for each item
  - Pagination controls (prev/next, page count)
  - State filter tabs: All | Draft | In Clarification | In Review | Ready | Exported
  - Loading state: skeleton placeholders (not spinner)
  - Empty state: "No work items yet. Create one to get started."
  - Error state: error banner with retry button
- [ ] Implement URL-synced filters: state filter reflected in query params (`?state=in_review`)

### WorkItemCard Component (`src/components/work-items/work-item-card.tsx`)

Props:
```typescript
interface WorkItemCardProps {
  workItem: WorkItemResponse
}
```

- [ ] [RED] Write component tests: renders title, type badge, state chip, completeness bar, derived state indicator (BLOCKED badge when `derived_state = blocked`)
- [ ] [GREEN] Implement `WorkItemCard`:
  - `TypeBadge`: colored chip per type (8 distinct colors)
  - `StateChip`: state name, color-coded by severity (draft=gray, ready=green, exported=blue)
  - `DerivedStateBadge`: shown only when `derived_state = blocked` (warning color)
  - `CompletenessBar`: 0-100 fill, percentage label
  - Owner avatar (initial fallback)
  - Click → navigates to `/workspace/{slug}/work-items/{id}`

---

## Phase 5 — Work Item Detail Page

Page: `src/app/workspace/[slug]/work-items/[id]/page.tsx`

- [ ] [RED] Write page tests: renders work item fields, shows state transition controls, shows suspended owner warning, shows override badge when `has_override = true`
- [ ] [GREEN] Implement `WorkItemDetailPage`:
  - Uses `useWorkItem(id)` for data
  - Renders `WorkItemHeader` (from EP-02 — placeholder here)
  - Renders `StateTransitionPanel`
  - Renders `OwnerPanel`
  - Loading: skeleton layout
  - 404 → renders "Work item not found" with back button

### StateTransitionPanel (`src/components/work-items/state-transition-panel.tsx`)

Props:
```typescript
interface StateTransitionPanelProps {
  workItem: WorkItemResponse
  onTransitionSuccess: (updated: WorkItemResponse) => void
}
```

- [ ] [RED] Write component tests: shows available transitions for current state, disabled when `owner_suspended_flag = true`, shows reason input for `changes_requested` transitions, force-ready button shown only for owner
- [ ] [GREEN] Implement `StateTransitionPanel`:
  - Derives available target states from current state (hardcoded valid transitions map in frontend)
  - Each transition rendered as a button
  - Optional reason text input
  - Force-ready button opens `ForceReadyModal`
  - Calls `useTransitionState()` or `useForceReady()` on action
  - Disabled state + loading spinner during mutation

### Acceptance Criteria — StateTransitionPanel

WHEN `workItem.state = "draft"` and current user is owner
THEN exactly one transition button is rendered: "Start Clarification" (target: `in_clarification`)
AND no "Force Ready" button is shown (not a valid target from draft)

WHEN `workItem.owner_suspended_flag = true`
THEN all transition buttons are disabled
AND a warning message is displayed explaining the owner is suspended

WHEN a transition to `changes_requested` is triggered
THEN a reason text input appears before the confirm button
AND the confirm button is disabled until the reason is non-empty

WHEN `useTransitionState()` mutation is pending
THEN all transition buttons are disabled and a loading spinner is shown
AND a second click on any button does NOT submit a second request

WHEN `useTransitionState()` resolves with HTTP 422 `INVALID_TRANSITION`
THEN an inline error is displayed (not a redirect)
AND the work item state displayed is NOT changed

### ForceReadyModal (`src/components/work-items/force-ready-modal.tsx`)

Props:
```typescript
interface ForceReadyModalProps {
  workItemId: string
  isOpen: boolean
  onClose: () => void
  onSuccess: (updated: WorkItemResponse) => void
}
```

- [ ] [RED] Write component tests: submit disabled until justification is non-empty (min 10 chars), submit button disabled until confirmation checkbox checked, shows API error inline on failure
- [ ] [GREEN] Implement `ForceReadyModal`:
  - Justification textarea (required, min 10 chars)
  - Confirmation checkbox: "I understand this bypasses pending validations"
  - Submit calls `forceReady()` with `{ justification, confirmed: true }`
  - Shows inline error on 403 or 422

### Acceptance Criteria — ForceReadyModal

WHEN the modal is open and justification has 9 chars and checkbox is checked
THEN the Submit button is disabled (min 10 chars not met)

WHEN justification has 10+ chars but the confirmation checkbox is unchecked
THEN the Submit button is disabled

WHEN justification has 10+ chars AND checkbox is checked
THEN the Submit button is enabled

WHEN Submit is clicked and `forceReady()` returns HTTP 422 `CONFIRMATION_REQUIRED`
THEN an inline error is shown listing the pending validation names
AND the modal stays open

WHEN Submit is clicked and `forceReady()` returns HTTP 403
THEN an inline error reads "You do not have permission to force this item to ready"
AND the modal stays open

WHEN `forceReady()` resolves with success
THEN `onSuccess(updatedWorkItem)` is called
AND the modal closes

---

## Phase 6 — Owner Reassignment

### OwnerPanel (`src/components/work-items/owner-panel.tsx`)

Props:
```typescript
interface OwnerPanelProps {
  workItem: WorkItemResponse
  canReassign: boolean  // derived from auth context: is owner or admin
}
```

- [ ] [RED] Write tests: shows owner name + avatar, shows suspended warning when `owner_suspended_flag = true`, reassign button only visible when `canReassign = true`
- [ ] [GREEN] Implement `OwnerPanel`:
  - Displays current owner avatar + name
  - Suspended owner: amber warning banner "Owner account suspended — reassignment recommended"
  - "Reassign" button opens `ReassignOwnerModal`

### ReassignOwnerModal

- [ ] [GREEN] Implement `ReassignOwnerModal`: user search input (workspace members), confirm button calls `reassignOwner()`, shows reason text field (optional)

---

## Phase 7 — Audit Trail Components

### TransitionHistory (`src/components/work-items/transition-history.tsx`)

Props: `{ workItemId: string }`

- [ ] [GREEN] Implement: fetches `GET /work-items/{id}/transitions`, renders timeline of state changes with actor, timestamp, reason, override badge for `is_override = true` entries
- [ ] Loading and empty states

### OwnershipHistory (`src/components/work-items/ownership-history.tsx`)

Props: `{ workItemId: string }`

- [ ] [GREEN] Implement: fetches `GET /work-items/{id}/ownership-history`, renders timeline of owner changes

---

## Phase 8 — Create Work Item Flow

Page: `src/app/workspace/[slug]/work-items/new/page.tsx`

- [ ] [GREEN] Implement `CreateWorkItemPage` (minimal — EP-02 extends with auto-save and templates):
  - Form: title input, type selector, optional description textarea
  - Submit calls `createWorkItem()`, redirects to new item's detail page on 201
  - Client-side validation: title min 3 chars, type required
  - Inline field errors on 422 response
  - Cancel button returns to list

### Acceptance Criteria — CreateWorkItemPage

WHEN the form is submitted with `title = "ab"` (2 chars)
THEN client-side validation blocks the submit
AND an inline error reads "Title must be at least 3 characters"
AND no API call is made

WHEN the form is submitted with no type selected
THEN client-side validation blocks the submit
AND an inline error reads "Type is required"

WHEN the form is submitted with valid data and API returns 201
THEN `router.push('/workspace/{slug}/work-items/{new_id}')` is called

WHEN the API returns 422 with `details.field = "title"`
THEN the title field shows the error message from `details`
AND the form is NOT reset (user can fix and resubmit)

WHEN the Cancel button is clicked
THEN `router.back()` is called (or navigate to `/workspace/{slug}/work-items`)
AND if the form has content, no confirmation is required (EP-02 adds this)

---

## Definition of Done

- [ ] All component and unit tests pass
- [ ] `tsc --noEmit` clean
- [ ] No `any` types in work item related code
- [ ] Work item list renders with state filters and pagination
- [ ] Detail page shows all fields, state transitions, owner panel
- [ ] Force-ready modal validates justification and confirmation before submitting
- [ ] Audit trail visible on detail page
- [ ] Loading, empty, and error states implemented on all pages and panels
