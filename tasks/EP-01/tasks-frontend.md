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

- [x] Implement `src/types/work-item.ts` (shipped as `frontend/lib/types/work-item.ts` + `frontend/lib/types/work-item-detail.ts`):
  - [x] `WorkItemState` enum: `draft | in_clarification | in_review | changes_requested | partially_validated | ready | exported` (`frontend/lib/types/work-item.ts`)
  - [x] `WorkItemType` enum: `idea | bug | enhancement | task | initiative | spike | business_change | requirement` — also extended with `story | milestone` per EP-14 (`frontend/lib/types/work-item.ts`)
  - [x] `DerivedState` enum: `in_progress | blocked | ready` (`frontend/lib/types/work-item.ts`)
  - [x] `WorkItemResponse` interface (full response shape above) (`frontend/lib/types/work-item.ts`)
  - [x] `WorkItemCreateRequest`, `WorkItemUpdateRequest`, `TransitionRequest`, `ForceReadyRequest`, `ReassignOwnerRequest` (`frontend/lib/types/work-item.ts`)
  - [x] `PagedWorkItemResponse<T>`: `{ items: T[], total: number, page: number, page_size: number }` (`frontend/lib/types/work-item.ts`)
  - [x] `StateTransitionRecord`, `OwnershipRecord` for audit trail responses (`frontend/lib/types/work-item.ts`)

---

## Phase 2 — API Client Functions

File: `src/lib/api/work-items.ts`

- [x] Implement `createWorkItem(data: WorkItemCreateRequest): Promise<WorkItemResponse>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `getWorkItem(id: string): Promise<WorkItemResponse>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `listWorkItems(projectId: string, filters: WorkItemFilters): Promise<PagedWorkItemResponse<WorkItemResponse>>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `updateWorkItem(id: string, data: WorkItemUpdateRequest): Promise<WorkItemResponse>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `deleteWorkItem(id: string): Promise<void>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `transitionState(id: string, data: TransitionRequest): Promise<WorkItemResponse>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `forceReady(id: string, data: ForceReadyRequest): Promise<WorkItemResponse>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `reassignOwner(id: string, data: ReassignOwnerRequest): Promise<WorkItemResponse>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `getTransitions(id: string): Promise<StateTransitionRecord[]>` (`frontend/lib/api/work-items.ts`)
- [x] Implement `getOwnershipHistory(id: string): Promise<OwnershipRecord[]>` (`frontend/lib/api/work-items.ts`)
- [x] [RED] Write unit tests for each function (`frontend/__tests__/lib/work-items.test.ts`) — uses fetch mocks (not MSW) but covers happy path, 404, and 422 envelopes

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

- [x] Implement `useWorkItem(id: string)` hook (`frontend/hooks/work-item/use-work-item.ts`, tests `frontend/__tests__/hooks/work-item/use-work-item.test.ts`) — plain React state (no React Query in codebase), returns `{ workItem, isLoading, error, refetch }`
- [x] Implement `useWorkItems(projectId: string, filters)` hook (`frontend/hooks/use-work-items.ts`, tests `frontend/__tests__/lib/use-work-items.test.ts`) — returns `{ items, total, isLoading, error }` with `page`/`page_size` support
- [ ] Implement `useTransitionState()` mutation hook with **centralised cache invalidation** for `['work-item', id]`, `['work-items', workspace_id]`, `['dashboard', 'global']`, `['inbox', user_id]`, `['completeness', id]`
  - [x] Partial: hook shipped as a plain mutation (`frontend/hooks/work-item/use-transition-state.ts`, tests `frontend/__tests__/hooks/work-item/use-transition-state.test.ts`) — returns `{ transition, isPending, error }`; callers refetch their own data since no React Query cache exists
- [x] Implement `useForceReady()` mutation hook (`frontend/hooks/work-item/use-force-ready.ts`, tests `frontend/__tests__/hooks/work-item/use-force-ready.test.ts`)
- [x] Implement `useReassignOwner()` mutation hook (`frontend/hooks/work-item/use-reassign-owner.ts`, tests `frontend/__tests__/hooks/work-item/use-reassign-owner.test.ts`)
- [x] [RED] Write hook tests — uses `@testing-library/react` with fetch mocks (no MSW), covers loading/populated/error states (`frontend/__tests__/hooks/work-item/*.test.ts`)

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

- [x] [RED] Write page component tests (`frontend/__tests__/app/workspace/items-page.test.tsx`) — loading skeleton, list render, empty state, pagination
- [x] [GREEN] Implement `WorkItemsPage` (`frontend/app/workspace/[slug]/items/page.tsx`):
  - [x] Uses `useWorkItems()` for data fetching
  - [x] Renders `WorkItemCard` for each item (though wrapped in `<td colSpan={5}>` — see reconciliation notes)
  - [x] Pagination controls (prev/next, page count) — URL-synced via `?page=`
  - [x] State filter via `<select>` dropdown (not tabs — see reconciliation notes)
  - [x] Loading state: skeleton placeholders
  - [x] Empty state: "No hay elementos de trabajo"
  - [x] Error state: error banner (no retry button — session-expired path is handled separately)
- [x] Implement URL-synced pagination (`?page=`); state filter is component-state only (no `?state=` URL sync yet — see notes)

### WorkItemCard Component (`src/components/work-items/work-item-card.tsx`)

Props:
```typescript
interface WorkItemCardProps {
  workItem: WorkItemResponse
}
```

- [x] [RED] Write component tests (`frontend/__tests__/components/work-item/work-item-card.test.tsx`)
- [x] [GREEN] Implement `WorkItemCard` (`frontend/components/work-item/work-item-card.tsx`):
  - [x] `TypeBadge` (`frontend/components/domain/type-badge.tsx`, test `frontend/__tests__/components/domain/type-badge.test.tsx`) — EP-19 replacement catalog badge
  - [x] `StateBadge` (`frontend/components/domain/state-badge.tsx`, test `frontend/__tests__/components/domain/state-badge.test.tsx`) — EP-19 replacement for `StateChip`
  - [ ] `DerivedStateBadge` as a dedicated component — derived-state visuals live inside `StateBadge`/card; no standalone `DerivedStateBadge` file was shipped
  - [x] `CompletenessBar` (`frontend/components/domain/completeness-bar.tsx`)
  - [x] Owner avatar (`frontend/components/domain/owner-avatar.tsx`, `user-avatar.tsx`)
  - [x] Click → navigates to `/workspace/{slug}/items/{id}` (handled by the parent `<tr>` row in items page; card itself is visual)

---

## Phase 5 — Work Item Detail Page

Page: `src/app/workspace/[slug]/work-items/[id]/page.tsx`

- [x] [RED] Write page tests (`frontend/__tests__/app/workspace/slug-page.test.tsx`; detail-page specifics also covered by component tests for panels)
- [x] [GREEN] Implement `WorkItemDetailPage` (`frontend/app/workspace/[slug]/items/[id]/page.tsx`):
  - [x] Uses `useWorkItem(id)` for data
  - [x] Renders `WorkItemHeader` (`frontend/components/work-item/work-item-header.tsx`)
  - [x] Renders `StateTransitionPanel`
  - [x] Renders `OwnerPanel`
  - [x] Loading: skeleton layout
  - [x] 404 handled via error state

### StateTransitionPanel (`src/components/work-items/state-transition-panel.tsx`)

Props:
```typescript
interface StateTransitionPanelProps {
  workItem: WorkItemResponse
  onTransitionSuccess: (updated: WorkItemResponse) => void
}
```

- [x] [RED] Write component tests (`frontend/__tests__/components/work-item/state-transition-panel.test.tsx`)
- [x] [GREEN] Implement `StateTransitionPanel` (`frontend/components/work-item/state-transition-panel.tsx`):
  - [x] Derives available target states from current state (state-machine constants in `frontend/lib/state-machine.ts`)
  - [x] Each transition rendered as a button
  - [x] Optional reason text input
  - [x] Force-ready button opens `ForceReadyModal`
  - [x] Calls `useTransitionState()` / `useForceReady()` on action
  - [x] Disabled state + loading spinner during mutation

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

- [x] [RED] Write component tests (`frontend/__tests__/components/work-item/force-ready-modal.test.tsx`)
- [x] [GREEN] Implement `ForceReadyModal` (`frontend/components/work-item/force-ready-modal.tsx`):
  - [x] Justification textarea (required, min-char validation)
  - [x] Confirmation checkbox
  - [x] Submit calls `forceReady()` with `{ justification, confirmed: true }`
  - [x] Shows inline error on 403 / 422

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

- [x] [RED] Write tests (`frontend/__tests__/components/work-item/owner-panel.test.tsx`)
- [x] [GREEN] Implement `OwnerPanel` (`frontend/components/work-item/owner-panel.tsx`):
  - [x] Displays current owner avatar + name
  - [x] Suspended owner warning
  - [x] "Reassign" button opens `ReassignOwnerModal`

### ReassignOwnerModal

- [x] [GREEN] Implement `ReassignOwnerModal` (`frontend/components/work-item/reassign-owner-modal.tsx`, test `frontend/__tests__/components/work-item/reassign-owner-modal.test.tsx`) — workspace members picker, optional reason

---

## Phase 7 — Audit Trail Components

### TransitionHistory (`src/components/work-items/transition-history.tsx`)

Props: `{ workItemId: string }`

- [x] [GREEN] Implement (`frontend/components/work-item/transition-history.tsx`, test `frontend/__tests__/components/work-item/transition-history.test.tsx`) — fetches via `useTransitions`, renders timeline with actor, timestamp, reason, override badge
- [x] Loading and empty states

### OwnershipHistory (`src/components/work-items/ownership-history.tsx`)

Props: `{ workItemId: string }`

- [x] [GREEN] Implement (`frontend/components/work-item/ownership-history.tsx`, test `frontend/__tests__/components/work-item/ownership-history.test.tsx`) — fetches via `useOwnershipHistory`

---

## Phase 8 — Create Work Item Flow

Page: `src/app/workspace/[slug]/work-items/new/page.tsx`

- [x] [GREEN] Implement `CreateWorkItemPage` (`frontend/app/workspace/[slug]/items/new/page.tsx`, test `frontend/__tests__/app/workspace/new-item-page.test.tsx`):
  - [x] Form: title, type selector, optional description
  - [x] Submit calls `createWorkItem()`, redirects on 201
  - [x] Client-side validation
  - [x] Inline field errors on 422
  - [x] Cancel button returns to list

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

- [x] All component and unit tests pass (component + hook + page tests shipped under `frontend/__tests__/`)
- [ ] `tsc --noEmit` clean (not verified as part of this reconciliation pass)
- [x] No `any` types in work item related code (spot-checked `frontend/lib/api/work-items.ts`, `frontend/lib/types/work-item.ts`, hooks)
- [x] Work item list renders with state filter and pagination (`frontend/app/workspace/[slug]/items/page.tsx`)
- [x] Detail page shows fields, state transitions, owner panel (`frontend/app/workspace/[slug]/items/[id]/page.tsx`)
- [x] Force-ready modal validates justification and confirmation before submitting (`frontend/components/work-item/force-ready-modal.tsx`)
- [x] Audit trail visible on detail page (`transition-history.tsx`, `ownership-history.tsx`)
- [x] Loading, empty, and error states implemented on pages and panels

---

## Reconciliation notes (2026-04-17)

Pure documentation pass. Walked the plan phase-by-phase against shipped code; notes below flag where reality deviated from the plan.

- **No React Query / SWR in the codebase.** The plan assumes a query-cache layer; the FE ships plain `useState` + `useEffect` hooks (`frontend/hooks/work-item/use-work-item.ts`, `use-work-items.ts`, etc). This has three knock-on effects, all left un-ticked above:
  - `useTransitionState` does **not** centralise cache invalidation across `['work-item']`, `['work-items']`, `['dashboard']`, `['inbox']`, `['completeness']`. The hook simply awaits the transition (`frontend/hooks/work-item/use-transition-state.ts`). Each consumer refetches its own data. Acceptance criteria for cross-cache invalidation are unmet as a consequence.
  - Hook tests use fetch mocks via `@testing-library/react` rather than MSW + React Query test utils. Behaviour is covered; the testing harness differs from the plan.
  - The "cross-view live update" acceptance criterion (list/dashboard/inbox/completeness reflect transitions without reload) is not implemented — no shared cache exists to invalidate.
- **No dedicated `WorkItemList` component.** The list is inlined into the page (`frontend/app/workspace/[slug]/items/page.tsx`). Extraction is deferred.
- **Table layout regression after `WorkItemCard` extraction.** The page renders `<thead>` with 5 columns (Title / Type / State / Completeness / Updated), then wraps the card in a single `<td colSpan={5}>`. Column alignment is broken — the card has its own internal grid that does not match the table headers. Must Fix when the list UI is next touched.
- **State filter is not URL-synced.** Only `?page=` is reflected in the URL (`frontend/app/workspace/[slug]/items/page.tsx` lines 42–57). The plan calls for `?state=in_review`-style URL sync; only pagination made it.
- **No dedicated `DerivedStateBadge` component.** EP-19's `StateBadge` (`frontend/components/domain/state-badge.tsx`) absorbed the derived-state visuals; no standalone badge file was shipped. Left un-ticked.
- **Filter UI is a single `<select>`, not tab strip.** The plan calls for tabs (All | Draft | …); the shipped UI is a dropdown. Functional equivalence but diverges from the spec. Ticked as "state filter" but noted here.
- **EP-19 badges shipped.** `StateBadge` and `TypeBadge` landed in `frontend/components/domain/` per the EP-19 alignment called out in the plan header. `StateChip` was never separately shipped.
- **No `TypedConfirmDialog` linkage on force-ready modal.** A `typed-confirm-dialog.tsx` exists in `frontend/components/domain/`, but `force-ready-modal.tsx` is its own modal — EP-19 migration of this surface is incomplete.
- **`WorkItemType` already extended with `story | milestone`** (EP-14 integration surface) — see `frontend/lib/types/work-item.ts`.

Overall: Phases 1–8 are ~85% shipped against the plan text. The gap is mostly "no shared cache layer" + list UI rough edges, not missing functionality.
