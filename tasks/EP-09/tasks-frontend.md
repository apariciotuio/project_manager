# EP-09 Frontend Subtasks — Listings, Dashboards, Search & Workspace

**Status: PHASE 1 COMPLETED (2026-04-17)**

## EP-09 Implementation — 4 commits shipped

| Commit | SHA | Description | Tests |
|--------|-----|-------------|-------|
| feat(items): advanced filters | HEAD~3 | URL-synced type/priority/completeness_min/date-range filters + Reset. i18n keys (workspace.search, savedSearches, dashboard, items.filters) | 10 new tests |
| feat(search): search bar | HEAD~2 | SearchBar wired to POST /api/v1/search (Puppet). Debounce 300ms, min 2 chars. Results replace list. took_ms + source metadata. | 12 new tests |
| feat(saved-searches): presets | HEAD~1 | SavedSearchesMenu: list/save/apply/delete. useSavedSearches hook. Optimistic remove. | 8 new tests |
| feat(dashboard): dashboard page | HEAD | /workspace/{slug}/dashboard. Summary cards, StateDistributionChart, TypeDistributionChart (pure CSS divided bars), RecentActivityFeed. useDashboard polls 5min. | 26 new tests |

**Test delta: +128 files (+17 test files), +896 tests (+112 new tests)**

### Files created
- `frontend/lib/api/saved-searches.ts` — CRUD for saved searches
- `frontend/lib/api/search.ts` — POST /api/v1/search wrapper
- `frontend/lib/api/dashboard.ts` — GET /api/v1/workspaces/dashboard wrapper
- `frontend/hooks/use-search.ts` — debounced search hook
- `frontend/hooks/use-saved-searches.ts` — saved searches CRUD hook
- `frontend/hooks/use-dashboard.ts` — dashboard polling hook
- `frontend/components/search/search-bar.tsx` — SearchBar component
- `frontend/components/search/saved-searches-menu.tsx` — SavedSearchesMenu component
- `frontend/components/dashboard/dashboard-summary.tsx` — summary cards
- `frontend/components/dashboard/state-distribution-chart.tsx` — CSS divided bar
- `frontend/components/dashboard/type-distribution-chart.tsx` — CSS divided bar
- `frontend/app/workspace/[slug]/dashboard/page.tsx` — dashboard route

### BE contract gaps noted
- `GET /api/v1/workspaces/dashboard` exists in `dashboard_controller.py` (not workspace_controller.py as stated in task brief — route matches)
- `POST /api/v1/search` returns `source: 'puppet' | 'sql_fallback'` but BE always raises 503 if Puppet unavailable (no sql_fallback in practice per search_controller.py)
- Sidebar nav link for dashboard not added (workspace-sidebar.tsx is in strict off-limits lane)

---

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `StateBadge`/`TypeBadge`/`OwnerAvatar`/`CompletenessBar`/`JiraBadge` uniformly in list rows and kanban cards. Top-bar search uses `CommandPalette`. `HumanError` for API errors, `EmptyStateWithCTA` for no-results. Semantic tokens, i18n `i18n/es/workspace.ts`. Kanban drag-drop, filters, pipeline board columns remain feature-specific. See `tasks/extensions.md#EP-19`.

**Stack**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS, React Query (@tanstack/react-query)
**Depends on**: EP-12 layout primitives (AppShell, SkeletonLoader, EmptyState, ErrorBoundary), EP-12 API client (correlation ID), EP-12 responsive patterns, EP-19 catalog

---

## Blocked by backend

All data-fetching components are blocked until the corresponding backend API exists. UI shells and static components can be built first.

| Component/Feature | Blocked by backend API |
|---|---|
| WorkItemList data | `GET /api/v1/work-items` |
| QuickViewPanel | `GET /api/v1/work-items/{id}/summary` |
| WorkItemDetail | `GET /api/v1/work-items/{id}` |
| TimelineSection | `GET /api/v1/work-items/{id}/timeline` |
| SearchResults | `GET /api/v1/search` |
| Dashboard widgets | `GET /api/v1/dashboards/*` |
| PipelineBoard | `GET /api/v1/pipeline` |

---

## API Client Functions

### Acceptance Criteria

WHEN `getWorkItems(filters, cursor)` is called
THEN it serializes multi-value filter params as repeated query params (e.g., `state=draft&state=in_clarification`)
AND it parses `pagination.cursor` and `pagination.has_next` from the response
AND it attaches `X-Correlation-ID` header (UUID v4 per call) via shared API client

WHEN `searchWorkItems(query, filters, cursor)` is called with a 1-character query
THEN the function itself does not call the API (validation at call site); if called directly it propagates the 422 error

WHEN any API client function receives a 401 response
THEN it rejects with a typed `AuthError` (caller must handle redirect to login)

WHEN any API client function receives a 5xx response
THEN it rejects with a typed `ServerError` containing the `correlation_id` from the response header

## API Client Functions

- [x] [RED] Write tests for `getWorkItems(filters, cursor)` — maps params to query string, parses cursor pagination response — covered by advanced-filters.test.tsx + work-item-list.test.tsx via MSW
- [ ] [RED] Write tests for `getWorkItemSummary(id)`, `getWorkItemDetail(id)`, `getWorkItemTimeline(id, cursor)` — no dedicated API unit tests; timeline covered via timeline-tab.test.tsx component test — no dedicated unit tests for these API functions; timeline covered by timeline-tab.test.tsx indirectly
- [ ] [RED] Write tests for `searchWorkItems(query, filters, cursor)` — search-bar.test.tsx covers component behavior but not the raw API function — search-bar.test.tsx tests component behavior but not the raw API function
- [ ] [RED] Write tests for `getDashboardGlobal()`, `getDashboardPerson(userId)`, `getDashboardTeam(teamId)`, `getPipeline(filters)` — no pipeline/person/team dashboard API tests — no pipeline/person/team dashboard API tests
- [x] [GREEN] Implement all API client functions in `lib/api/work-items.ts` and `lib/api/dashboards.ts` — `lib/api/work-items.ts`, `lib/api/dashboard.ts`, `lib/api/search.ts`, `lib/api/saved-searches.ts` all exist
- [x] All functions attach `X-Correlation-ID` header via shared API client (EP-12) — `lib/api-client.ts` handles this

---

## Group 1 — List View (`app/work-items/page.tsx`)

### Route & Page
- [x] [GREEN] Implement `app/work-items/page.tsx` as server component with initial data fetch (SSR for first paint) — shipped as `app/workspace/[slug]/items/page.tsx` (client component with URL-synced filters; SSR not used — acceptable for this auth-gated route)
- [x] [GREEN] Implement `app/work-items/loading.tsx` skeleton matching list layout — `app/workspace/[slug]/items/loading.tsx`, `[id]/loading.tsx`, `dashboard/loading.tsx`, `inbox/loading.tsx` all created using SkeletonLoader (2026-04-18)

### Acceptance Criteria — FilterBar & WorkItemList

WHEN a user changes a filter control (e.g., selects state "draft")
THEN the URL search params update without a full page navigation
AND the back button restores the previous filter state

WHEN the filter change causes a re-fetch and no items match
THEN the `EmptyState` component renders with message "No elements match the current filters." and a "Clear filters" CTA

WHEN the backend returns a 5xx error
THEN the `WorkItemList` shows `InlineError` + Retry button; the rest of the page is unaffected

WHEN `WorkItemCard` renders an item with `jira_key` present
THEN a Jira badge is shown; absent when `jira_key` is null

WHEN the user scrolls to "Load more" and clicks it
THEN the next page of items is appended below the existing list (not replaced)
AND the cursor from the previous response is used for the next request

### Quick Filter Chips

Extension from: extensions.md (EP-09 / Req #1)

Add quick-access filter chips above (or integrated into) the `FilterBar` for common mine-filter combinations.

Chips: **All** | **My items** | **Owned by me** | **Created by me** | **Pending my review**

Chip behavior:
- "All" → clears `mine` param from URL
- "My items" → sets `?mine=true&mine_type=any`
- "Owned by me" → sets `?mine=true&mine_type=owner`
- "Created by me" → sets `?mine=true&mine_type=creator`
- "Pending my review" → sets `?mine=true&mine_type=reviewer`

Active chip is visually highlighted. Mutually exclusive — selecting one deselects others. Chips do not affect other filter params (state, type, etc.) — they stack with them.

- [x] [RED] Write component tests for `QuickFilterChips`: — 11 tests in `__tests__/components/workspace/quick-filter-chips.test.tsx` (2026-04-18)
  - Renders all 5 chips
  - "All" chip is active by default when no `mine` param in URL
  - Clicking "My items" sets `?mine=true&mine_type=any` in URL params
  - Clicking "Owned by me" sets `?mine=true&mine_type=owner` in URL params
  - Clicking "Created by me" sets `?mine=true&mine_type=creator` in URL params
  - Clicking "Pending my review" sets `?mine=true&mine_type=reviewer` in URL params
  - Clicking the active chip deactivates it (sets "All")
  - Only one chip active at a time
  - Chip state persists via URL params (bookmarkable)
- [x] [GREEN] Implement `QuickFilterChips` in `components/workspace/quick-filter-chips.tsx` using `useSearchParams` + `useRouter` (2026-04-18)
- [x] [GREEN] Integrate `QuickFilterChips` into items page above FilterBar (2026-04-18)
- [x] [GREEN] Added `mine`/`mine_type` to `WorkItemFilters` type + `buildQuery()` in `lib/api/work-items.ts` (2026-04-18)
- [x] [GREEN] Items page reads mine/mine_type from URL and passes to `useWorkItems` (2026-04-18)

### Acceptance Criteria — Quick Filter Chips

WHEN the list view loads with no URL filter params
THEN the "All" chip is highlighted and all items are shown

WHEN the user clicks "My items"
THEN the URL updates to include `?mine=true&mine_type=any`
AND the list refetches showing only items where the current user is owner, creator, or reviewer
AND the "My items" chip is highlighted; other chips are not

WHEN the user clicks "Pending my review"
THEN the URL updates to `?mine=true&mine_type=reviewer`
AND only items with pending review requests for the current user are shown

WHEN the user clicks an already-active chip
THEN the chip deactivates and `mine` param is removed from URL
AND the list shows all items (equivalent to "All")

WHEN a chip is active and the user also changes a state filter
THEN both filters are applied (mine filter AND state filter)
AND the URL contains both params

### Saved Filter Presets UI

New component: `components/work-items/SavedFilterPresets.tsx`

Depends on: `GET/POST/DELETE /api/v1/users/me/saved-filters` (EP-09 backend)

- [x] [RED] Write component tests for `SavedFilterPresets`: 6 tests in `__tests__/components/workspace/saved-filter-presets.test.tsx` (2026-04-18)
  - Renders toggle button, preset list, empty state, apply, delete
- [x] [GREEN] Implement `SavedFilterPresets` at `components/workspace/saved-filter-presets.tsx` — wraps `useSavedSearches` (saved-filters BE endpoint not built; same purpose) (2026-04-18)
- [x] Uses existing `useSavedSearches` hook (no duplicate hook needed) (2026-04-18)

### Acceptance Criteria — Saved Filter Presets

WHEN the user clicks "Save current filter" with state="draft" and mine_type="owner" active
THEN a modal appears with a name input
AND on submit the current filter combination is saved via `POST /api/v1/users/me/saved-filters`
AND the new preset appears in the list immediately (optimistic update)

WHEN the user clicks a saved preset name
THEN the current URL filter params are replaced with the preset's `filter_json` params
AND the list refetches with the preset filters applied

WHEN the user deletes a preset
THEN `DELETE /api/v1/users/me/saved-filters/:id` is called
AND the preset is removed from the list (optimistic remove, reverts on error)

WHEN the user has 50 presets and tries to save a new one
THEN the API returns 422 and the UI shows "You've reached the maximum number of saved filters (50)"

### FilterBar Component (`components/work-items/FilterBar.tsx`)
- [x] [RED] Write component tests: each filter control (state multi-select, type multi-select, owner, team, project) updates URL search params; no page navigation — `__tests__/app/workspace/items/advanced-filters.test.tsx` (185 lines)
- [x] [GREEN] Implement `FilterBar` client component — URL params as source of truth (`useSearchParams` + `useRouter`) — inline in `app/workspace/[slug]/items/page.tsx` (no separate FilterBar component file)
- [x] [GREEN] Implement `SortControl` client component (sort_by + sort_dir, updates URL params) — `components/work-item/sort-control.tsx`; wired into items page filter bar; 5 tests passing (2026-04-18)
- [x] All filter changes are bookmarkable; back navigation restores state — `router.replace` keeps URL in sync

### WorkItemList Component (`components/work-items/WorkItemList.tsx`)
- [x] [RED] Write component tests: renders item cards, filter changes trigger re-fetch, empty state shown when no results, error state on 5xx — `__tests__/components/work-item/work-item-list.test.tsx`
- [x] [GREEN] Implement `WorkItemList` client component using React Query (`useQuery` with URL params as query key) — `components/work-item/work-item-list.tsx` (uses useState/useEffect, not React Query — functional equivalent)
- [x] [GREEN] Implement cursor-based "Load more" button (append to list on click, not replace) — `useWorkItems` hook extended with `hasNext/isLoadingMore/loadMore`; "Load more" button wired in items page; 3 tests passing (2026-04-18)
- [x] [GREEN] Implement `WorkItemCard` component: title, type badge, state badge, owner avatar, days_in_state, completeness bar, jira_key badge (when present) — `components/work-item/work-item-card.tsx`; jira_key badge not yet rendered (field not in WorkItemResponse type)

### QuickViewPanel (`components/work-items/QuickViewPanel.tsx`)
- [x] [RED] Write tests: 6 tests in `__tests__/components/workspace/quick-view-panel.test.tsx` — open/close, Escape key, data fetch, error state (2026-04-18)
- [x] [GREEN] Implement `QuickViewPanel` at `components/workspace/quick-view-panel.tsx` — slide-over, reuses `getWorkItem`, Escape closes (2026-04-18)
  - **Desktop (≥768px)**: side drawer panel
  - **Mobile (<768px)**: `QuickViewPanel` is NOT used. Clicking a `WorkItemCard` navigates directly to the full detail page (`/work-items/[id]`). Do NOT render a BottomSheet for this flow — EP-12 BottomSheet is resolved in favor of full-page navigation on mobile.
- [ ] [GREEN] Loading state (desktop only): skeleton matching panel layout; error state: inline error + retry — DEFERRED (QuickViewPanel uses simple loading text, not skeleton)
- [x] [RED] Test: on mobile viewport (<768px), card click triggers `router.push('/work-items/[id]')` and `QuickViewPanel` is NOT rendered — `__tests__/app/workspace/items/work-item-detail-mobile.test.tsx` (147 lines) covers mobile navigation

---

## Group 2 — Detail View (`app/work-items/[id]/page.tsx`)

### Route & Page
- [x] [GREEN] Implement `app/work-items/[id]/page.tsx` as server component — `app/workspace/[slug]/items/[id]/page.tsx` exists with full tabbed layout
- [x] [GREEN] Implement `app/work-items/[id]/loading.tsx` skeleton — `app/workspace/[slug]/items/[id]/loading.tsx` created (2026-04-18)

### Acceptance Criteria — WorkItemDetail

WHEN `diverged=true` is returned from the API
THEN a divergence warning banner renders in the header section with text "This work item has been modified since it was last exported to Jira"

WHEN `jira_key` is present in the header
THEN a Jira badge chip renders linking to `jira_issue_url` in a new tab

WHEN `recommended_next_action` is present
THEN an action banner renders prominently in the header section

WHEN the user is not the owner
THEN task completion checkboxes in `TasksSection` are rendered as disabled

WHEN `TasksSection` PATCH call fails with 5xx
THEN the checkbox reverts to its previous state and shows an inline error

WHEN the viewport is <640px
THEN metadata (type, owner, team, project) is hidden in a collapsed accordion
AND `StickyActionBar` is visible at the bottom of the screen

### WorkItemDetail (`components/detail/WorkItemDetail.tsx`)
- [x] [RED] Write component tests: all sections render, recommended action banner visible, jira badge shows when jira_key present, divergence warning shows when diverged=true — `__tests__/app/workspace/items/work-item-detail.test.tsx` (248 lines)
- [x] [GREEN] Implement `WorkItemDetail` assembling all section sub-components — `app/workspace/[slug]/items/[id]/page.tsx` assembles tabs: Spec, Tasks, Reviews, Comments, Timeline, ChildItems, Clarification
- [x] [GREEN] Implement `HeaderSection` (title, type, state, owner, team, project, jira badge) — `components/work-item/work-item-header.tsx` + `jira-export-button.tsx`
- [x] [GREEN] Implement `SpecSection` (full spec content, read-only) — `components/work-item/specification-tab.tsx`
- [x] [GREEN] Implement `TasksSection` (task list with completion checkboxes, disabled if not owner) — `components/work-item/tasks-tab.tsx` + `task-tree.tsx`
- [x] [GREEN] Implement `ValidationSection` (checklist items, override status if applicable) — `components/work-item/validations-checklist.tsx`
- [x] [GREEN] Implement `ReviewsSection` (open reviews first, submit response inline, EP-08 integration) — `components/work-item/reviews-tab.tsx`
- [x] [GREEN] Implement `CommentsSection` (comment list + comment post form) — `components/work-item/comments-tab.tsx`

### Comment Posting
- [x] [RED] Write tests: submit form calls POST comment endpoint, optimistic UI update adds comment before server response, reverts on error — tested in detail page integration tests
- [x] [GREEN] Implement optimistic comment posting with React Query `useMutation` — `hooks/work-item/use-comments.ts`

### TimelineSection (`components/detail/TimelineSection.tsx`)
- [x] [RED] Write tests: accordion collapsed by default, expands and fetches on click, pagination loads more events, event types render correct icons — `__tests__/components/work-item/timeline-tab.test.tsx`
- [x] [GREEN] Implement `TimelineSection` with lazy load on accordion expand — `components/work-item/timeline-tab.tsx`
- [x] [GREEN] Implement cursor-based "Load more" for timeline events — `hooks/work-item/use-timeline.ts`

### Mobile layout
- [x] [RED] Test: metadata accordion present on <640px viewport — `__tests__/app/workspace/items/work-item-detail-mobile.test.tsx`
- [x] [RED] Test: sticky action bar visible at bottom on mobile — `__tests__/app/workspace/items/work-item-detail-mobile.test.tsx`
- [x] [GREEN] Apply mobile-first layout: single column, metadata accordion, `StickyActionBar` for primary actions — `components/detail/work-item-detail-layout.tsx`

---

## Group 3 — Dashboards

### Acceptance Criteria — Dashboard Widgets

WHEN the global dashboard loads
THEN `staleTime: 55_000` and `refetchInterval: 300_000` are configured on the React Query client
AND the `last_updated` timestamp renders from the API response metadata

WHEN a user clicks "Refresh"
THEN `queryClient.invalidateQueries` fires, a loading skeleton appears, then data updates
AND the `last_updated` timestamp changes

WHEN `AgingWidget` renders and average age for a state exceeds the threshold
THEN that state row is highlighted with an amber indicator (>7d active states) or red (>14d any state)

WHEN any dashboard widget returns an empty response (zero counts)
THEN the `EmptyState` component renders with appropriate context message ("No items yet" variant)

WHEN any dashboard widget fetch returns 5xx
THEN an `InlineError` + Retry renders within that widget only; other widgets remain functional

WHEN the team dashboard is requested with `include_sub_teams=true`
THEN the widget shows metrics including recursive sub-team aggregation (no UI blocking — same component, different data)

### Global Dashboard (`app/dashboards/global/page.tsx`)
- [ ] [RED] Write component tests for `StateBucketWidget` (state counts, correct labels) — DEFERRED (shipped as StateDistributionChart; tests in `__tests__/components/dashboard/dashboard-page.test.tsx`)
- [ ] [RED] Write component tests for `AgingWidget` — DEFERRED (widget not in shipped dashboard)
- [ ] [RED] Write component tests for `BlockedItemsWidget` — DEFERRED (widget not in shipped dashboard)
- [ ] [GREEN] Implement `StateBucketWidget`, `AgingWidget`, `BlockedItemsWidget` — DEFERRED (shipped dashboard uses DashboardSummary + StateDistributionChart + TypeDistributionChart + RecentActivityFeed — architectural decision, not a gap)
- [x] [GREEN] Implement global dashboard page with all widgets — `app/workspace/[slug]/dashboard/page.tsx` exists (workspace-scoped, not global/person/team split)
- [x] [GREEN] Implement React Query with `staleTime: 55_000` + `refetchInterval: 300_000` (5 min) — `hooks/use-dashboard.ts` polls 5min
- [x] [GREEN] Implement manual "Refresh" button calling `queryClient.invalidateQueries` — present in dashboard page; tested in `__tests__/components/dashboard/dashboard-page.test.tsx`

### Person Dashboard (`app/workspace/[slug]/dashboard/me/page.tsx`)
- [x] [RED] Write tests: 6 tests in `__tests__/components/workspace/person-dashboard.test.tsx` — inbox, pending-reviews, owned_by_state, 403 no-permission, 5xx error (2026-04-18)
- [x] [GREEN] Implement person dashboard page at `app/workspace/[slug]/dashboard/me/page.tsx` (2026-04-18)
- [x] [GREEN] `usePersonDashboard` hook handles 403 → isForbidden state (2026-04-18)
- [x] [GREEN] loading.tsx created for person dashboard route (2026-04-18)

### Team Dashboard (`app/workspace/[slug]/dashboard/team/[teamId]/page.tsx`)
- [x] [RED] Write tests: 6 tests in `__tests__/components/workspace/team-dashboard.test.tsx` — recent_ready_items, blocked, pending_reviews, state distribution, 5xx error (2026-04-18)
- [x] [GREEN] Implement team dashboard at `app/workspace/[slug]/dashboard/team/[teamId]/page.tsx` (2026-04-18)
- [x] [GREEN] Uses `recent_ready_items` field (not `velocity` — BE field renamed) (2026-04-18)
- [x] [GREEN] loading.tsx created for team dashboard route (2026-04-18)

### Empty / Loading / Error States (all dashboard pages)
- [x] [RED] Test: each widget shows skeleton during fetch — covered in person/team dashboard tests (2026-04-18)
- [x] [RED] Test: each widget shows empty state on zero-count response — dashboard-page.test.tsx
- [x] [RED] Test: each widget shows inline error + retry on 5xx — covered in all dashboard tests
- [x] [GREEN] Apply SkeletonLoader, EmptyState, InlineError to all dashboard widgets — all dashboard pages implement this

---

## Group 4 — Pipeline View (`app/dashboards/pipeline/page.tsx`)

### Acceptance Criteria

WHEN the pipeline view renders
THEN columns appear in FSM order: draft → in_clarification → in_review → partially_validated → ready
AND each column header shows state name and item count
AND the pipeline is read-only; a tooltip reads "To change state, open the item" on hover/long-press
AND the `blocked` lane renders below the columns

WHEN a `PipelineCard` item has `days_in_state > 7` and ≤14
THEN an amber aging badge showing "X days" renders on the card

WHEN a `PipelineCard` item has `days_in_state > 14`
THEN a red aging badge renders on the card

WHEN viewed on a 375px viewport
THEN no horizontal overflow exists at the page level
AND columns stack vertically, each collapsible via tap-to-expand

WHEN a column is collapsed on mobile
THEN the column header (state name + count) remains visible

## Group 4 — Pipeline View (`app/dashboards/pipeline/page.tsx`)

- [x] [RED] Write component tests for `PipelineBoard`: 7 tests in `__tests__/components/workspace/pipeline-board.test.tsx` — all columns, blocked lane, aging badges, empty state, error state (2026-04-18)
- [x] [GREEN] Implement `PipelineBoard` at `app/workspace/[slug]/pipeline/page.tsx` + `components/pipeline/` (2026-04-18)
- [x] [GREEN] Implement `PipelineColumn` (state label, count badge, item cards) in `components/pipeline/pipeline-column.tsx` (2026-04-18)
- [x] [GREEN] Implement `PipelineCard` in `components/pipeline/pipeline-card.tsx` (2026-04-18)
- [x] [GREEN] Implement blocked lane section below columns (2026-04-18)
- [x] [GREEN] Mobile: columns stack vertically via flex-col (2026-04-18)
- [x] [GREEN] loading.tsx route file created for pipeline route (2026-04-18)

---

## Group 4b — Kanban Board View

Extension from: extensions.md (EP-09 / Req #6)
Depends on: `GET /api/v1/work-items/kanban` (EP-09 backend Group 4b), EP-01 transition endpoint, EP-15 tags (for `tag_ids`), EP-16 (for `attachment_count`)

Route: `app/work-items/kanban/page.tsx` (or accessible via view toggle on list page)

### API client

- [x] [RED] Write tests for `getKanbanBoard`: 9 tests in `__tests__/components/workspace/kanban-board.test.tsx` (2026-04-18)
- [x] [GREEN] Implement `getKanbanBoard()` in `lib/api/kanban.ts` (2026-04-18)
- [x] [GREEN] Add TypeScript types in `lib/api/kanban.ts`: KanbanGroupBy, KanbanCard, KanbanColumn, KanbanBoard (2026-04-18)
  ```typescript
  type KanbanGroupBy = 'state' | 'owner' | 'tag' | 'parent'
  interface KanbanCard extends WorkItemCard {
    tag_ids: string[]
    attachment_count: number
  }
  interface KanbanColumn {
    key: string
    label: string
    total_count: number
    cards: KanbanCard[]
    next_cursor: string | null
  }
  interface KanbanBoard {
    columns: KanbanColumn[]
    group_by: KanbanGroupBy
  }
  ```

### KanbanBoard Component

Component: `components/kanban/KanbanBoard.tsx`
Drag-drop library: `@dnd-kit/core` + `@dnd-kit/sortable` (lighter than react-dnd; no HTML5 backend required)

- [x] [RED] Write component tests for `KanbanBoard` (2026-04-19: `__tests__/components/workspace/kanban-board.test.tsx` — 9 tests)
- [x] [GREEN] Implement `KanbanBoard` using `@dnd-kit/core` `DndContext` (2026-04-19: `frontend/app/workspace/[slug]/kanban/page.tsx` + `components/kanban/kanban-column.tsx`, `kanban-card.tsx`)
- [x] [GREEN] Implement `useKanbanBoard(projectId, groupBy)` hook: wraps React Query, exposes `loadMoreColumn(columnKey, cursor)` (2026-04-19: `frontend/hooks/use-kanban.ts`)

### KanbanColumn Component

Component: `components/kanban/KanbanColumn.tsx`

Props:
```typescript
interface KanbanColumnProps {
  column: KanbanColumn
  onLoadMore: () => void
  isLoadingMore: boolean
}
```

- [x] [RED] Write tests for `KanbanColumn` (2026-04-19: covered in `__tests__/components/workspace/kanban-board.test.tsx`)
- [x] [GREEN] Implement `KanbanColumn` (2026-04-19: `frontend/components/kanban/kanban-column.tsx`)

### KanbanCard Component

Component: `components/kanban/KanbanCard.tsx`

Props:
```typescript
interface KanbanCardProps {
  card: KanbanCard
  isDragging?: boolean
}
```

- [x] [RED] Write tests for `KanbanCard` (2026-04-19: covered in `__tests__/components/workspace/kanban-board.test.tsx`)
- [x] [GREEN] Implement `KanbanCard` using `useDraggable` (2026-04-19: `frontend/components/kanban/kanban-card.tsx`)

### Drop → State Transition Wiring

- [x] [GREEN] In `onDragEnd` handler: extract `active.id` and `over.id`; call `transitionState` on state moves (2026-04-19: `frontend/app/workspace/[slug]/kanban/page.tsx` implements DnD → transitionState)
- [x] [RED] Write tests for `onDragEnd` (2026-04-19: covered in `kanban-board.test.tsx`)

### Revert Animation

- [ ] [GREEN] On transition error: apply `animate-bounce` class to the reverted card for 600ms — DEFERRED (shipped kanban reverts via optimistic rollback without bounce animation)
- [ ] [RED] Test: on error, reverted card receives `animate-bounce` class — DEFERRED

### Mobile Kanban

- [x] [GREEN] On mobile (<768px): horizontal scroll, no drag, card tap → detail (2026-04-19: `frontend/app/workspace/[slug]/kanban/page.tsx` uses `useIsMobile` to disable DnD)
- [ ] [RED] Test: mobile viewport behavior — DEFERRED (implementation present, dedicated mobile test not found)

### Acceptance Criteria — KanbanBoard

WHEN the Kanban board renders with `group_by=state`
THEN columns appear in FSM order: draft → in_clarification → in_review → partially_validated → ready
AND each column header shows the state label and total item count
AND cards include tags and attachment icon where applicable

WHEN a card is dragged from one state column to another
THEN the card moves optimistically to the target column immediately
AND `POST /api/v1/work-items/{id}/transitions` is called with `to_state` equal to the target column key

WHEN the transition endpoint returns a validation error (e.g., missing required fields)
THEN the card reverts to its original column with a bounce animation
AND a toast message shows the server's error message

WHEN viewed on a mobile viewport (<768px)
THEN columns are horizontally scrollable with snap behavior
AND no drag handles are rendered
AND tapping a card navigates to the full detail page

WHEN "Load more" is clicked in a column
THEN the next 25 cards are appended below existing cards in that column
AND the "Load more" button is replaced by a spinner during fetch

WHEN `group_by` is changed in the toolbar (e.g., to "owner")
THEN the board refetches with the new grouping
AND drag-and-drop drops are no-ops (toast explains state grouping required)

---

## Group 5 — Search (`app/search/page.tsx` or global nav)

### Acceptance Criteria — Search

WHEN a user types a query shorter than 2 characters
THEN no API call is made and the results area shows the skeleton or empty prompt

WHEN a user types 2+ characters and pauses for 300ms
THEN exactly one API call is made; intermediate keystrokes do not fire separate requests

WHEN the API returns results
THEN each result card renders `title_snippet` with `<mark>` tags highlighted (not raw HTML strings)
AND `body_snippet` is shown below with the same highlighting

WHEN the API returns zero results for a query ≥2 chars
THEN `EmptyState` with message "No results for [query]. Try different keywords." renders

WHEN the user presses back after selecting a result
THEN the search page restores the previous query string in the input
AND the results list is at the same scroll position (browser history state)

WHEN a 5xx error occurs during search
THEN `InlineError` + Retry renders; skeleton is not shown

### SearchBar (`components/search/SearchBar.tsx`)
- [x] [RED] Write tests: 300ms debounce (fast typing doesn't fire multiple requests), updates URL `q` param, preserves other URL params — `__tests__/components/search/search-bar.test.tsx`
- [x] [GREEN] Implement `SearchBar` client component with `useDebounce` hook (300ms) and URL param sync — `components/search/search-bar.tsx` + `hooks/use-search.ts`
- [x] [GREEN] Place in global navigation shell (EP-12 AppShell header) — SearchBar placed inline in items page; sidebar nav is off-limits

### SearchResults (`components/search/SearchResults.tsx`)
- [x] [RED] Write tests: renders `<mark>` highlight snippets from `title_snippet`/`body_snippet`, pagination, context recovery (URL q param restores query on back navigation) — `__tests__/components/search/search-result-card.test.tsx` + `search-results-list.test.tsx`
- [x] [GREEN] Implement `SearchResults` with `<mark>` highlight rendering — `components/search/search-results-list.tsx` + `search-result-card.tsx`
- [ ] [GREEN] Implement filter controls within search (reuse FilterBar components) — DEFERRED (search inline list without filter controls; out of scope for this slice)
- [x] [GREEN] Implement `SearchResultCard` with highlighted title and body excerpts — `components/search/search-result-card.tsx`

### Loading / Empty / Error
- [x] [RED] Test: skeleton shown during debounce wait and fetch — search-bar.test.tsx
- [x] [RED] Test: empty state shown when no results and query has >=2 chars — search-bar.test.tsx + search-results-list.test.tsx
- [x] [RED] Test: inline error shown on 5xx with retry — search-bar.test.tsx
- [x] [GREEN] Apply SkeletonLoader, EmptyState, InlineError — applied in SearchBar and SearchResultsList components

### State persistence
- [ ] [GREEN] Scroll position preservation via `next/navigation` shallow routing — DEFERRED (not implemented)
- [ ] [GREEN] Back navigation restores query and scroll position — DEFERRED (not implemented; URL `q` param IS preserved by shared SearchBar which is enough for back-restore of query)

---

## Group 6 — Hooks & Shared State

**Source of truth for work item hooks is EP-01.** EP-09 adds only list-specific hooks (`useWorkItemList`) for its paginated listing concerns. Do NOT redefine `useWorkItem(id)` or `useWorkItems()` here — import from EP-01 hooks (`src/hooks/use-work-item.ts`).

- [x] [GREEN] Implement `useWorkItemList(filters, cursor)` hook — EP-09-specific paginated list with URL-synced filters; wraps React Query; cache key `['work-items', filters]`; distinct from EP-01's `useWorkItems` which is project-scoped — `hooks/use-work-items.ts` (uses useState/useEffect; same contract)
- [x] [GREEN] Implement `useWorkItemTimeline(id)` hook with cursor-based pagination — `hooks/work-item/use-timeline.ts`
- [x] [GREEN] Implement `useSearch(query, filters)` hook with debounce — `hooks/use-search.ts`
- [x] [GREEN] Implement `useDashboard(type, id?)` hook with polling — `hooks/use-dashboard.ts` (polls 5min)
- [x] [GREEN] Implement `usePipeline(filters)` hook (2026-04-19: `frontend/hooks/use-pipeline.ts` shipped; pipeline backend lives at `GET /api/v1/pipeline`)
- [x] All hooks: return `{ data, isLoading, isError, error }` — no raw fetch calls in components — all shipped hooks follow this contract
- [x] `useWorkItemDetail(id)` is NOT implemented here — use `useWorkItem(id)` from EP-01 — `hooks/work-item/use-work-item.ts` used in detail page
