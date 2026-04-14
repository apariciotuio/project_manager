# EP-09 Frontend Subtasks — Listings, Dashboards, Search & Workspace

**Stack**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS, React Query (@tanstack/react-query)
**Depends on**: EP-12 layout primitives (AppShell, SkeletonLoader, EmptyState, ErrorBoundary), EP-12 API client (correlation ID), EP-12 responsive patterns

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

- [ ] [RED] Write tests for `getWorkItems(filters, cursor)` — maps params to query string, parses cursor pagination response
- [ ] [RED] Write tests for `getWorkItemSummary(id)`, `getWorkItemDetail(id)`, `getWorkItemTimeline(id, cursor)`
- [ ] [RED] Write tests for `searchWorkItems(query, filters, cursor)`
- [ ] [RED] Write tests for `getDashboardGlobal()`, `getDashboardPerson(userId)`, `getDashboardTeam(teamId)`, `getPipeline(filters)`
- [ ] [GREEN] Implement all API client functions in `lib/api/work-items.ts` and `lib/api/dashboards.ts`
- [ ] All functions attach `X-Correlation-ID` header via shared API client (EP-12)

---

## Group 1 — List View (`app/work-items/page.tsx`)

### Route & Page
- [ ] [GREEN] Implement `app/work-items/page.tsx` as server component with initial data fetch (SSR for first paint)
- [ ] [GREEN] Implement `app/work-items/loading.tsx` skeleton matching list layout

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

### FilterBar Component (`components/work-items/FilterBar.tsx`)
- [ ] [RED] Write component tests: each filter control (state multi-select, type multi-select, owner, team, project) updates URL search params; no page navigation
- [ ] [GREEN] Implement `FilterBar` client component — URL params as source of truth (`useSearchParams` + `useRouter`)
- [ ] [GREEN] Implement `SortControl` client component (sort_by + sort_dir, updates URL params)
- [ ] All filter changes are bookmarkable; back navigation restores state

### WorkItemList Component (`components/work-items/WorkItemList.tsx`)
- [ ] [RED] Write component tests: renders item cards, filter changes trigger re-fetch, empty state shown when no results, error state on 5xx
- [ ] [GREEN] Implement `WorkItemList` client component using React Query (`useQuery` with URL params as query key)
- [ ] [GREEN] Implement cursor-based "Load more" button (append to list on click, not replace)
- [ ] [GREEN] Implement `WorkItemCard` component: title, type badge, state badge, owner avatar, days_in_state, completeness bar, jira_key badge (when present)

### QuickViewPanel (`components/work-items/QuickViewPanel.tsx`)
- [ ] [RED] Write tests: opens on card click (desktop only), fetches summary, renders title/type/state/description excerpt/recommended action, closes on Escape and overlay click
- [ ] [GREEN] Implement `QuickViewPanel` as slide-over panel (client component)
  - **Desktop (≥768px)**: side drawer panel
  - **Mobile (<768px)**: `QuickViewPanel` is NOT used. Clicking a `WorkItemCard` navigates directly to the full detail page (`/work-items/[id]`). Do NOT render a BottomSheet for this flow — EP-12 BottomSheet is resolved in favor of full-page navigation on mobile.
- [ ] [GREEN] Loading state (desktop only): skeleton matching panel layout; error state: inline error + retry
- [ ] [RED] Test: on mobile viewport (<768px), card click triggers `router.push('/work-items/[id]')` and `QuickViewPanel` is NOT rendered

---

## Group 2 — Detail View (`app/work-items/[id]/page.tsx`)

### Route & Page
- [ ] [GREEN] Implement `app/work-items/[id]/page.tsx` as server component
- [ ] [GREEN] Implement `app/work-items/[id]/loading.tsx` skeleton

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
- [ ] [RED] Write component tests: all sections render, recommended action banner visible, jira badge shows when jira_key present, divergence warning shows when diverged=true
- [ ] [GREEN] Implement `WorkItemDetail` assembling all section sub-components
- [ ] [GREEN] Implement `HeaderSection` (title, type, state, owner, team, project, jira badge)
- [ ] [GREEN] Implement `SpecSection` (full spec content, read-only)
- [ ] [GREEN] Implement `TasksSection` (task list with completion checkboxes, disabled if not owner)
- [ ] [GREEN] Implement `ValidationSection` (checklist items, override status if applicable)
- [ ] [GREEN] Implement `ReviewsSection` (open reviews first, submit response inline, EP-08 integration)
- [ ] [GREEN] Implement `CommentsSection` (comment list + comment post form)

### Comment Posting
- [ ] [RED] Write tests: submit form calls POST comment endpoint, optimistic UI update adds comment before server response, reverts on error
- [ ] [GREEN] Implement optimistic comment posting with React Query `useMutation`

### TimelineSection (`components/detail/TimelineSection.tsx`)
- [ ] [RED] Write tests: accordion collapsed by default, expands and fetches on click, pagination loads more events, event types render correct icons
- [ ] [GREEN] Implement `TimelineSection` with lazy load on accordion expand
- [ ] [GREEN] Implement cursor-based "Load more" for timeline events

### Mobile layout
- [ ] [RED] Test: metadata accordion present on <640px viewport
- [ ] [RED] Test: sticky action bar visible at bottom on mobile
- [ ] [GREEN] Apply mobile-first layout: single column, metadata accordion, `StickyActionBar` for primary actions

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
- [ ] [RED] Write component tests for `StateBucketWidget` (state counts, correct labels)
- [ ] [RED] Write component tests for `AgingWidget` (amber/red thresholds applied, correct item count)
- [ ] [RED] Write component tests for `BlockedItemsWidget` (blocked items with pre-block state)
- [ ] [GREEN] Implement `StateBucketWidget`, `AgingWidget`, `BlockedItemsWidget`
- [ ] [GREEN] Implement global dashboard page with all widgets
- [ ] [GREEN] Implement React Query with `staleTime: 55_000` + `refetchInterval: 300_000` (5 min)
- [ ] [GREEN] Implement manual "Refresh" button calling `queryClient.invalidateQueries`

### Person Dashboard (`app/dashboards/person/[userId]/page.tsx`)
- [ ] [RED] Write tests for `ReviewActivityWidget` (pending reviews count, overload indicator >5 in_clarification)
- [ ] [GREEN] Implement `ReviewActivityWidget` and person dashboard page

### Team Dashboard (`app/dashboards/team/[teamId]/page.tsx`)
- [ ] [RED] Write tests for `TeamVelocityWidget` (items completed last 30d, blocked count)
- [ ] [GREEN] Implement `TeamVelocityWidget` and team dashboard page

### Empty / Loading / Error States (all dashboard pages)
- [ ] [RED] Test: each widget shows skeleton during fetch
- [ ] [RED] Test: each widget shows empty state on zero-count response
- [ ] [RED] Test: each widget shows inline error + retry on 5xx
- [ ] [GREEN] Apply SkeletonLoader, EmptyState, InlineError to all dashboard widgets

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

- [ ] [RED] Write component tests for `PipelineBoard`: all state columns rendered, items capped at 20, blocked lane visible, aging badges (amber/red) rendered
- [ ] [RED] Write tests for `PipelineCard`: title, type, owner, days_in_state, aging indicator
- [ ] [GREEN] Implement `PipelineBoard` with horizontal scroll on mobile
- [ ] [GREEN] Implement `PipelineColumn` (state label, count badge, item cards, collapsed on mobile with tap-to-expand)
- [ ] [GREEN] Implement `PipelineCard`
- [ ] [GREEN] Implement `BlockedLane` section below columns
- [ ] [GREEN] Implement filter controls at top of pipeline (reuse `FilterBar` components, URL params)
- [ ] [RED] Test: pipeline renders without horizontal overflow on 375px viewport (vertical column stack on mobile)
- [ ] [GREEN] Mobile: stack columns vertically, each collapsible

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
- [ ] [RED] Write tests: 300ms debounce (fast typing doesn't fire multiple requests), updates URL `q` param, preserves other URL params
- [ ] [GREEN] Implement `SearchBar` client component with `useDebounce` hook (300ms) and URL param sync
- [ ] [GREEN] Place in global navigation shell (EP-12 AppShell header)

### SearchResults (`components/search/SearchResults.tsx`)
- [ ] [RED] Write tests: renders `<mark>` highlight snippets from `title_snippet`/`body_snippet`, pagination, context recovery (URL q param restores query on back navigation)
- [ ] [GREEN] Implement `SearchResults` with `<mark>` highlight rendering
- [ ] [GREEN] Implement filter controls within search (reuse FilterBar components)
- [ ] [GREEN] Implement `SearchResultCard` with highlighted title and body excerpts

### Loading / Empty / Error
- [ ] [RED] Test: skeleton shown during debounce wait and fetch
- [ ] [RED] Test: empty state shown when no results and query has >=2 chars
- [ ] [RED] Test: inline error shown on 5xx with retry
- [ ] [GREEN] Apply SkeletonLoader, EmptyState, InlineError

### State persistence
- [ ] [GREEN] Scroll position preservation via `next/navigation` shallow routing
- [ ] [GREEN] Back navigation restores query and scroll position

---

## Group 6 — Hooks & Shared State

**Source of truth for work item hooks is EP-01.** EP-09 adds only list-specific hooks (`useWorkItemList`) for its paginated listing concerns. Do NOT redefine `useWorkItem(id)` or `useWorkItems()` here — import from EP-01 hooks (`src/hooks/use-work-item.ts`).

- [ ] [GREEN] Implement `useWorkItemList(filters, cursor)` hook — EP-09-specific paginated list with URL-synced filters; wraps React Query; cache key `['work-items', filters]`; distinct from EP-01's `useWorkItems` which is project-scoped
- [ ] [GREEN] Implement `useWorkItemTimeline(id)` hook with cursor-based pagination
- [ ] [GREEN] Implement `useSearch(query, filters)` hook with debounce
- [ ] [GREEN] Implement `useDashboard(type, id?)` hook with polling
- [ ] [GREEN] Implement `usePipeline(filters)` hook
- [ ] All hooks: return `{ data, isLoading, isError, error }` — no raw fetch calls in components
- [ ] `useWorkItemDetail(id)` is NOT implemented here — use `useWorkItem(id)` from EP-01
