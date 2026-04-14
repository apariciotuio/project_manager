# Tasks: EP-09 — Listings, Dashboards, Search & Workspace

> **Scope (2026-04-14, decisions_pending.md #4/#9/#24/#28)**: Search delegated to **Puppet** (see `specs/search/spec.md` + EP-13). No PG FTS, no `search_vector`, no `tsvector`, no GIN index, no denormalized aggregated columns, no Elasticsearch. Listings/filters/sorts stay in SQL.

**Status**: Not started
**Last updated**: 2026-04-14 (EP polish)

---

## Phase 1: Data Layer & Migrations

- [ ] Add `state_entered_at TIMESTAMPTZ` column to `work_items` if not present (migration)
- [ ] Add composite indexes: `(state, updated_at DESC)`, `(owner_id, updated_at DESC)`, `(team_id, updated_at DESC)`, `(state, owner_id, updated_at DESC)`
- [ ] Add index on `work_items_history (item_id, created_at DESC)` for timeline queries
- [ ] **[REFACTOR]** Verify all migrations are idempotent and reversible

---

## Phase 2: Saved Searches (decision #24)

- [ ] **[RED]** Write tests for `saved_searches` table (id, workspace_id, user_id, name, query, filters JSONB, created_at, updated_at)
- [ ] **[GREEN]** Create migration for `saved_searches` with `idx_saved_searches_user ON (workspace_id, user_id)`
- [ ] **[RED]** Write unit tests for `SavedSearchService.create/list/rename/delete`
- [ ] **[GREEN]** Implement `SavedSearchService` and `GET/POST/PATCH/DELETE /api/v1/saved-searches`

---

## Phase 3: List API (US-090)

- [ ] **[RED]** Write tests for `GET /api/v1/work-items` with no filters (default behavior, archived excluded)
- [ ] **[RED]** Write tests for each filter: state, owner_id, type, team_id, project (unit + integration)
- [ ] **[RED]** Write tests for filter combinations (AND logic)
- [ ] **[RED]** Write tests for `owner_id=me` and `team_id=mine` resolution
- [ ] **[RED]** Write tests for cursor-based pagination (cursor encoding, next_cursor=null on last page, limit cap at 100)
- [ ] **[RED]** Write tests for sort options (all 5 fields, asc/desc, invalid sort returns 422)
- [ ] **[RED]** Write tests for `include_archived=true` behavior
- [ ] Implement `WorkItemListQueryBuilder` in application layer
- [ ] Implement cursor encode/decode utilities (`encode_cursor`, `decode_cursor`)
- [ ] Implement `GET /api/v1/work-items` controller with full filter/sort/pagination
- [ ] **[GREEN]** All list API tests pass
- [ ] **[REFACTOR]** Extract filter validation into `WorkItemListFilters` Pydantic model

---

## Phase 4: Quick View API (US-090)

- [ ] **[RED]** Write tests for `GET /api/v1/work-items/{id}/summary` (happy path, 404, 403)
- [ ] **[RED]** Write tests for summary payload fields (all required fields present, description truncated at 300 chars)
- [ ] Implement `WorkItemSummaryService.get_summary(item_id, user)` with minimal projection query
- [ ] Implement `GET /api/v1/work-items/{id}/summary` controller
- [ ] **[GREEN]** All summary tests pass

---

## Phase 5: Unified Detail View (US-095)

- [ ] **[RED]** Write tests for `GET /api/v1/work-items/{id}` full payload (all sections present)
- [ ] **[RED]** Write tests for each section: tasks, validation_requirements, review_requests+responses, comments
- [ ] **[RED]** Write tests for recommended next action logic (all 5 state/condition branches)
- [ ] **[RED]** Write tests for 401/403 access control
- [ ] Implement `WorkItemDetailService.get_detail(item_id, user)` using `selectinload` for all relationships
- [ ] Implement recommended next action resolver (`NextActionResolver`)
- [ ] Implement `GET /api/v1/work-items/{id}` controller
- [ ] **[GREEN]** All detail tests pass
- [ ] **[RED]** Write tests for `GET /api/v1/work-items/{id}/timeline` (pagination, event types)
- [ ] Implement timeline query service (paginated, cursor-based)
- [ ] Implement `GET /api/v1/work-items/{id}/timeline` controller
- [ ] **[GREEN]** All timeline tests pass
- [ ] **[REFACTOR]** Verify no N+1 queries in detail assembly (check SQLAlchemy query log in tests)

---

## Phase 6: Search API (US-094) — Puppet delegation

- [ ] **[RED]** Write tests for `GET /api/v1/search?q=...` — calls `PuppetClient.search(q, tag=wm_<workspace_id>, filters)` and returns ranked results with snippets
- [ ] **[RED]** Write tests for prefix / type-ahead (decision #24) — `GET /api/v1/search/suggest?q=...`
- [ ] **[RED]** Write tests for query validation (empty → 422, < 2 chars → 422)
- [ ] **[RED]** Write tests for facet filters (state, type, team_id, owner_id) forwarded to Puppet as tag filters
- [ ] **[RED]** Write tests for `include_archived` toggle → Puppet tag `archived:true|false`
- [ ] **[RED]** Write tests for pagination of Puppet results
- [ ] **[RED]** Write tests for result scoping — workspace tag `wm_<workspace_id>` always enforced server-side (user never chooses workspace)
- [ ] **[RED]** Write tests for degraded mode: when Puppet is unavailable, return `503` with `error.code = "SEARCH_UNAVAILABLE"` (no local fallback — no FTS exists)
- [ ] Implement `SearchService` as a thin wrapper around `PuppetClient` (EP-13)
- [ ] Implement `GET /api/v1/search` controller with rate limiting (30 req/min per user)
- [ ] **[GREEN]** All search tests pass

---

## Phase 7: Dashboard APIs (US-091, US-092)

- [ ] **[RED]** Write tests for global dashboard aggregation query (state counts, avg_age_days)
- [ ] **[RED]** Write tests for Redis cache behavior (cache hit returns cached data, cache miss triggers query)
- [ ] **[RED]** Write tests for cache invalidation on work_item state change
- [ ] **[RED]** Write tests for aging thresholds (configurable via env vars)
- [ ] Implement `GlobalDashboardService.get_metrics()` with Redis cache + on-demand query
- [ ] Implement cache invalidation hook in `WorkItemFSMService` (after state transition)
- [ ] Implement `GET /api/v1/dashboards/global` controller
- [ ] **[GREEN]** Global dashboard tests pass
- [ ] **[RED]** Write tests for by-person dashboard (happy path, zero-state, 404 for unknown user)
- [ ] **[RED]** Write tests for inbox counts on self-view
- [ ] **[RED]** Write tests for overload indicator (> 5 items in in_clarification)
- [ ] Implement `PersonDashboardService.get_metrics(user_id, requesting_user)`
- [ ] Implement `GET /api/v1/dashboards/person/{user_id}` controller
- [ ] **[GREEN]** By-person dashboard tests pass
- [ ] **[RED]** Write tests for by-team dashboard (happy path, pending reviews, velocity widget, 404)
- [ ] **[RED]** Write tests for `include_sub_teams=true` recursive aggregation
- [ ] Implement `TeamDashboardService.get_metrics(team_id)` with optional recursive mode
- [ ] Implement `GET /api/v1/dashboards/team/{team_id}` controller
- [ ] **[GREEN]** By-team dashboard tests pass
- [ ] **[REFACTOR]** Extract shared cache key management into `DashboardCacheService`

---

## Phase 8: Pipeline API (US-093)

- [ ] **[RED]** Write tests for pipeline data (all states returned, counts correct, items capped at 20 per column)
- [ ] **[RED]** Write tests for aging indicators (amber > 7 days, red > 14 days)
- [ ] **[RED]** Write tests for blocked lane (blocked items with pre-block state)
- [ ] **[RED]** Write tests for filter parameters in pipeline (same filter params as list view)
- [ ] **[RED]** Write tests for Redis cache with filter_hash key
- [ ] Implement `PipelineQueryService.get_pipeline(filters)` using grouped query with `json_agg`
- [ ] Implement `filter_hash` generation (deterministic SHA-256 of sorted filter params)
- [ ] Implement `GET /api/v1/pipeline` controller
- [ ] **[GREEN]** All pipeline tests pass

---

## Phase 9: Frontend — List View (US-090)

- [ ] **[RED]** Write component tests for `WorkItemList` (renders items, filter changes update URL params)
- [ ] **[RED]** Write tests for `FilterBar` (each filter control updates URL params correctly)
- [ ] **[RED]** Write tests for `QuickViewPanel` (opens on item click, shows summary data, closes)
- [ ] Implement `WorkItemList` server component with initial data fetch
- [ ] Implement `FilterBar` client component (state, type, owner, team, project filters)
- [ ] Implement `SortControl` client component
- [ ] Implement cursor-based infinite scroll or "Load more" button
- [ ] Implement `QuickViewPanel` slide-over with `GET .../summary` call
- [ ] **[GREEN]** All list view component tests pass

---

## Phase 10: Frontend — Unified Detail (US-095)

- [ ] **[RED]** Write component tests for `WorkItemDetail` (all sections render, recommended action logic)
- [ ] **[RED]** Write tests for `TimelineSection` (lazy loads on expand, pagination)
- [ ] **[RED]** Write tests for `CommentsSection` (renders comments, post comment updates list)
- [ ] **[RED]** Write tests for `ReviewsSection` (open reviews shown first, submit response)
- [ ] Implement `WorkItemDetail` server component
- [ ] Implement all section sub-components
- [ ] Implement `TimelineSection` with lazy load on accordion expand
- [ ] Implement comment posting with optimistic UI update
- [ ] Implement Jira badge (renders only when `jira_key` present)
- [ ] **[GREEN]** All detail view tests pass

---

## Phase 11: Frontend — Dashboards (US-091, US-092, US-093)

- [ ] **[RED]** Write component tests for `StateBucketWidget`, `AgingWidget`, `BlockedItemsWidget`
- [ ] **[RED]** Write tests for `ReviewActivityWidget`, `TeamVelocityWidget`
- [ ] **[RED]** Write tests for `PipelineBoard` (columns rendered, blocked lane visible, aging badges)
- [ ] Implement global dashboard page with all widgets
- [ ] Implement by-person dashboard page
- [ ] Implement by-team dashboard page
- [ ] Implement `PipelineBoard` with `PipelineColumn` and `BlockedLane`
- [ ] Implement React Query polling (5 min interval) and manual refresh
- [ ] **[GREEN]** All dashboard and pipeline component tests pass

---

## Phase 12: Frontend — Search (US-094)

- [ ] **[RED]** Write component tests for `SearchBar` (debounce 150ms, prefix-suggest on keystroke, updates URL params)
- [ ] **[RED]** Write tests for `SearchResults` (renders highlight snippets from Puppet, pagination)
- [ ] **[RED]** Write tests for `SavedSearches` panel — list / save-current / delete
- [ ] **[RED]** Write tests for context recovery (query preserved in URL, back navigation restores state)
- [ ] Implement `SearchBar` with prefix suggest (calls `/api/v1/search/suggest`) and URL param sync
- [ ] Implement `SearchResults` with `<mark>` highlight rendering from Puppet snippets
- [ ] Implement `SavedSearches` side panel with CRUD
- [ ] Implement filter controls within search (reuse `FilterBar` components; filters become Puppet facet tags)
- [ ] Implement browser history state for scroll position preservation
- [ ] Implement degraded-search banner when backend returns 503 `SEARCH_UNAVAILABLE`
- [ ] **[GREEN]** All search UI tests pass

---

## Phase 13: Integration & Performance Validation

- [ ] Run `EXPLAIN ANALYZE` on all critical listing/filter queries; verify index usage
- [ ] Load test list API with 10k items — verify P95 < 200ms
- [ ] Search perf is Puppet's responsibility; verify our wrapper adds <50ms overhead (stub Puppet + measure)
- [ ] Load test dashboard endpoints — verify cache hit P95 < 150ms
- [ ] Verify no N+1 queries in any endpoint (SQLAlchemy query counting in integration tests)
- [ ] Verify all endpoints return 401 for unauthenticated requests
- [ ] Verify access scoping (user cannot access items outside their scope)

---

## Phase 14: Review Gate

- [ ] Run `code-reviewer` agent on all new backend code
- [ ] Run `code-reviewer` agent on all new frontend code
- [ ] Run `review-before-push` workflow
- [ ] Address all Must Fix findings

---

**Status: NOT STARTED** — 2026-04-13
