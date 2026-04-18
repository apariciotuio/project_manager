# EP-09 Backend Subtasks — Listings, Dashboards, Search & Workspace

> **Scope (2026-04-14, decisions_pending.md #4/#9/#24/#28)**: Search is delegated to **Puppet** (see EP-13 `PuppetClient`). No PG FTS, no `search_vector`, no `tsvector`, no GIN, no `pg_trgm` for FTS. This file has been rewritten — Group 1 (schema) drops FTS columns, Group 2 (indexing) is replaced by Puppet push-on-write hooks, the Search API group wraps `PuppetClient`. Saved searches are a local feature per decision #24.

**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery
**Depends on**: EP-12 middleware stack (correlation ID, rate limit, auth), EP-01 FSM (state_entered_at), EP-04 (versioning), EP-00 (JWT), EP-13 (PuppetClient + sync pipeline)

---

## API Contract (interface for frontend)

### List endpoint
```
GET /api/v1/work-items
    ?state=draft&state=in_clarification
    &owner_id=me
    &type=story
    &team_id={uuid}
    &project={string}
    &sort_by=updated_at
    &sort_dir=desc
    &limit=25
    &cursor={opaque_cursor}
    &include_archived=false

Response 200:
{
  "data": [WorkItemCard],
  "pagination": { "cursor": "base64", "has_next": true, "total_count": 142 },
  "applied_filters": { "state": ["draft"], "owner_id": "uuid" }
}
WorkItemCard: { id, title, type, state, owner_id, team_id, project, updated_at,
                completeness, days_in_state, jira_key?, diverged? }
Errors: 401, 403, 422 (invalid filter/sort/limit)
```

### Detail endpoint
```
GET /api/v1/work-items/{id}
Response 200: { header, spec, tasks[], validation_checklist[], reviews[], comments[],
                recommended_next_action, diverged, last_export_version_id? }
Errors: 401, 403, 404

GET /api/v1/work-items/{id}/summary
Response 200: { id, title, type, state, owner_id, completeness,
                description_excerpt (max 300 chars), recommended_next_action }
Errors: 401, 403, 404

GET /api/v1/work-items/{id}/timeline
    ?cursor={cursor}&limit=50
Response 200: { events[], pagination }
Event: { id, event_type, actor_id, actor_name, created_at, payload }
```

### Search endpoint
```
GET /api/v1/search
    ?q={query}&state=...&type=...&team_id=...&owner_id=...
    &include_archived=false&cursor={cursor}&limit=20
Response 200: { data: [SearchResultItem], pagination }
SearchResultItem: { id, title, type, state, owner_id, team_id,
                    rank, title_snippet, body_snippet }
Errors: 401, 422 (q < 2 chars or empty)
Rate limit: 30 req/min per user (429)
```

### Dashboard endpoints
```
GET /api/v1/dashboards/global
Response 200: { states: [{state, count, avg_age_days}],
                blocked_count, aging_warnings, aging_criticals }

GET /api/v1/dashboards/person/{user_id}
Response 200: { owned_by_state: [{state, count}], inbox_count,
                overloaded: bool, pending_reviews_count }

GET /api/v1/dashboards/team/{team_id}
    ?include_sub_teams=false
Response 200: { owned_by_state, pending_reviews, velocity_last_30d,
                blocked_count }

GET /api/v1/pipeline
    ?state=...&owner_id=...&team_id=...&project=...
Response 200: { columns: [{ state, count, avg_age_days,
                  items: [PipelineCard (max 20)] }],
                blocked_lane: [BlockedItem] }
```

---

## Group 1 — Migrations & Indexes

### Acceptance Criteria

WHEN migrations run against a clean PostgreSQL 16 database
THEN `state_entered_at TIMESTAMPTZ` column exists on `work_items`
AND composite indexes `(state, updated_at DESC)`, `(owner_id, updated_at DESC)`, `(team_id, updated_at DESC)`, `(state, owner_id, updated_at DESC)` all exist
AND index on `work_items_history(item_id, created_at DESC)` exists
AND `saved_searches` table exists with `idx_saved_searches_user ON (workspace_id, user_id)`

WHEN any migration is rolled back
THEN the rollback completes without error and the schema is identical to the pre-migration state

WHEN EXPLAIN ANALYZE is run on `SELECT ... WHERE state = $1 ORDER BY updated_at DESC LIMIT 25`
THEN the query plan uses an index scan, not a sequential scan

- [ ] [GREEN] Migration: add `state_entered_at TIMESTAMPTZ` column to `work_items` if not present (check EP-01) — skipped, EP-01 owns this
- [x] [GREEN] Add composite indexes: migration 0100 adds idx_work_items_state_updated, idx_work_items_owner_updated, idx_work_items_state_owner, idx_work_items_creator (2026-04-17)
- [ ] [GREEN] Add index on `work_items_history(item_id, created_at DESC)` for timeline queries — deferred (no history table yet)
- [x] [GREEN] Migration 0026: `saved_searches` table exists. Migration 0100: added `is_shared BOOL`. Indexes in place. (2026-04-17)
- [x] Do NOT add FTS — decision honored, Puppet-only (2026-04-17)
- [x] [REFACTOR] Migrations 0100 are idempotent (IF NOT EXISTS / IF NOT EXISTS) (2026-04-17)

---

## Group 2 — Puppet Indexing Hooks

### Acceptance Criteria

WHEN a work item's title/description/sections are updated within a transaction
THEN a Celery task `push_to_puppet(entity_type, entity_id, workspace_id)` is enqueued after commit (outbox/transactional-outbox pattern)
AND the task POSTs the entity payload to Puppet with tag `wm_<workspace_id>` (see EP-13 `PuppetClient.index`)

WHEN a comment or review response is created
THEN a Celery task enqueues a push to Puppet for the parent work_item (search scope includes comments per EP-13)

WHEN a comment or work_item is deleted
THEN a Celery task enqueues `PuppetClient.delete(entity_type, entity_id)`

- [ ] Push-on-write tasks live in EP-13 (see EP-13 `tasks-backend.md`). EP-09 only wires the SQLAlchemy `after_commit` hook that enqueues them.
- [ ] [RED] Write test asserting the `after_commit` hook enqueues the Puppet push task exactly once per committed change (not per flush)
- [ ] [GREEN] Implement the `after_commit` hook

---

## Group 3 — Domain & Application Layer

### Acceptance Criteria — Cursor Pagination Utilities

WHEN `encode_cursor(sort_value, id)` is called
THEN it returns an opaque base64-encoded string
AND `decode_cursor(encoded)` returns the original `(sort_value, id)` tuple

WHEN a tampered cursor string (not valid base64 or wrong signature) is passed to any list endpoint
THEN the API returns HTTP 422 with `error.code: invalid_cursor`
AND no partial results are returned

WHEN `limit=0` or `limit=101` is supplied
THEN the API returns HTTP 422; limit is capped at 100 for values between 1 and 100

WHEN `owner_id=me` is passed as a filter
THEN `WorkItemListFilters` resolves it to the authenticated user's UUID before query execution
AND the resolved UUID is echoed in `applied_filters.owner_id` in the response

### Cursor Pagination Utilities
- [x] [RED] 9 tests for encode/decode + tamper detection (2026-04-17)
- [x] [GREEN] PaginationCursor in domain/pagination.py — base64(json({sv, id})), tamper raises ValueError→422 (2026-04-17)
- [x] [GREEN] WorkItemListFilters Pydantic model — all filter params, completeness range validation, limit bounds (2026-04-17)

### WorkItemListQueryBuilder
- [x] [RED] 21 unit tests: no filters, each filter isolated, combinations, all sort options, cursor (2026-04-17)
- [x] [GREEN] WorkItemListQueryBuilder in application/services/work_item_list_service.py (2026-04-17)

### My Items Filter Extension

Support `?mine=true&mine_type=owner|creator|reviewer|any` query params on `GET /api/v1/work-items`.

Behavior when `mine=true`:
- `mine_type=owner` → `owner_id = current_user.id`
- `mine_type=creator` → `created_by = current_user.id`
- `mine_type=reviewer` → item has a pending `review_request` where `reviewer_id = current_user.id` OR `reviewer_type = 'team'` AND current user is a member of that team
- `mine_type=any` (default) → OR of all three conditions above

`mine=false` (default) → filter has no effect; all existing filters apply normally.

- [x] [RED] Write unit tests for `WorkItemListQueryBuilder` mine filter variants (2026-04-18 — 11 tests in test_mine_filter.py):
  - `mine=true&mine_type=owner` → SQL `owner_id = :user_id`
  - `mine=true&mine_type=creator` → SQL `created_by = :user_id`
  - `mine=true&mine_type=reviewer` → subquery on `review_requests` where `reviewer_id = :user_id OR (reviewer_type='team' AND team has current user)`
  - `mine=true&mine_type=any` → OR combination of all three
  - `mine=false` → no mine condition appended; existing filters unchanged
  - `mine=true` without `mine_type` → defaults to `any`
  - `mine=true&mine_type=invalid` → HTTP 422
- [x] [GREEN] Extend `WorkItemListFilters` Pydantic model: `mine: bool = False`, `mine_type: MineType = MineType.any`; added `MineType` enum (2026-04-18)
- [x] [GREEN] `WorkItemListQueryBuilder._apply_mine_filter()` with EXISTS subqueries on review_requests + team_memberships (2026-04-18)
- [x] [GREEN] Controller wired: `mine`, `mine_type` query params; passes `current_user_id` to service; `applied_filters` includes mine context (2026-04-18)
- [x] [REFACTOR] `_apply_mine_filter` is a clean dispatch — no if/elif monolith (2026-04-18)

### Saved Filter Presets

New endpoints:
```
GET    /api/v1/users/me/saved-filters
POST   /api/v1/users/me/saved-filters         body: { name: str, filter_json: dict }
DELETE /api/v1/users/me/saved-filters/:id
```

New table:
```sql
CREATE TABLE saved_filters (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name         VARCHAR(255) NOT NULL,
  filter_json  JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_saved_filters_user_workspace ON saved_filters (user_id, workspace_id);
```

Constraints: max 50 saved filters per user per workspace (enforce in service layer, return HTTP 422 with `error.code: saved_filter_limit_exceeded` if exceeded).

`filter_json` validated against `WorkItemListFilters` schema on write; reject invalid payloads with HTTP 422.

### Acceptance Criteria — My Items Filter

WHEN `GET /api/v1/work-items?mine=true&mine_type=owner` is called
THEN only items where `owner_id = current_user.id` are returned
AND `applied_filters` in the response includes `mine: { type: "owner", user_id: "<resolved_uuid>" }`

WHEN `GET /api/v1/work-items?mine=true&mine_type=reviewer` is called
THEN items are returned where the current user is a direct reviewer OR is a member of a team-type reviewer
AND items where the user is not a reviewer are excluded

WHEN `GET /api/v1/work-items?mine=true` is called (no mine_type)
THEN defaults to `mine_type=any` and returns items matching any ownership condition

WHEN `GET /api/v1/work-items?mine=true&mine_type=invalid` is called
THEN HTTP 422 is returned

WHEN `POST /api/v1/users/me/saved-filters` is called with valid `{ name, filter_json }`
THEN a new saved filter record is created and returned with its `id` and `created_at`

WHEN `POST /api/v1/users/me/saved-filters` is called and user already has 50 filters in the workspace
THEN HTTP 422 is returned with `error.code: saved_filter_limit_exceeded`

WHEN `POST /api/v1/users/me/saved-filters` is called with `filter_json` that fails `WorkItemListFilters` validation
THEN HTTP 422 is returned with validation details

WHEN `DELETE /api/v1/users/me/saved-filters/:id` is called for a filter owned by a different user
THEN HTTP 403 is returned

- [ ] [RED] Write migration test: `saved_filters` table exists with all columns; index `idx_saved_filters_user_workspace` exists
- [ ] [GREEN] Migration: create `saved_filters` table and index
- [ ] [RED] Write service tests for `SavedFilterService.list()`, `.create()`, `.delete()` including limit enforcement and ownership check
- [ ] [GREEN] Implement `SavedFilterService` in `application/services/saved_filter_service.py`
- [ ] [GREEN] Implement `SavedFilterRepository` in `infrastructure/persistence/saved_filter_repository.py`
- [ ] [RED] Write integration tests for `GET/POST/DELETE /api/v1/users/me/saved-filters`
- [ ] [GREEN] Implement saved filter controllers and routes

### Acceptance Criteria — WorkItemDetailService

WHEN `GET /api/v1/work-items/{id}` is called by an authenticated, authorized user
THEN the response contains all sections: header, spec, tasks, validation_checklist, reviews, comments, recommended_next_action, diverged, last_export_version_id
AND total SQLAlchemy query count is ≤5 (enforced in tests via query counter)

WHEN state=DRAFT and completeness<50%
THEN `recommended_next_action = "Complete specification"`

WHEN state=ENRICHMENT and open review requests exist
THEN `recommended_next_action` names the reviewer: "Respond to review request from [reviewer name]"

WHEN state=READY
THEN `recommended_next_action = "Item is ready — no action required"`

WHEN state=BLOCKED
THEN `recommended_next_action = "Resolve blocker: [blocker description]"`

WHEN an unauthenticated request is made
THEN the API returns HTTP 401

WHEN an authenticated user requests an item outside their scope
THEN the API returns HTTP 403 with no item data in the response body

WHEN the work item does not exist
THEN the API returns HTTP 404

### WorkItemDetailService
- [ ] [RED] Write tests for full payload assembly (all sections present, no N+1)
- [ ] [RED] Write tests for recommended next action resolver (all 5 state/condition branches)
- [ ] [RED] Write tests for 401/403 access control
- [ ] [GREEN] Implement `WorkItemDetailService.get_detail(item_id, user)` using `selectinload` for tasks, validation_requirements, review_requests+responses, comments
- [ ] [GREEN] Implement `NextActionResolver` (pure function — no persistence)
- [ ] [REFACTOR] Verify no N+1 by asserting SQLAlchemy query count <= 5 in tests

### WorkItemSummaryService
- [ ] [RED] Write tests: happy path, 404, 403, description truncated at 300 chars
- [ ] [GREEN] Implement `WorkItemSummaryService.get_summary(item_id, user)` with minimal projection

### TimelineService
- [ ] [RED] Write tests: pagination, event types, 404
- [ ] [GREEN] Implement `TimelineQueryService` with cursor-based pagination, indexed by `item_id + created_at`

### Acceptance Criteria — SearchService (Puppet wrapper)

WHEN a query of 2+ characters is submitted
THEN `SearchService.search(q, workspace_id, facets, cursor, limit)` calls `PuppetClient.search(q, tag=wm_<workspace_id>, facets, cursor, limit)` and returns Puppet's ranked results with snippets verbatim

WHEN the query contains fewer than 2 characters or is empty/whitespace-only
THEN the API returns HTTP 422 with a descriptive message (validated before Puppet call)

WHEN the query ends with `*` or is a prefix lookup
THEN the service calls `PuppetClient.prefix(...)` instead of `.search(...)` (decision #24)

WHEN `include_archived` is not supplied (default)
THEN the Puppet tag filter includes `archived:false`

WHEN `include_archived=true` is supplied
THEN the `archived` tag filter is not constrained

WHEN the same user exceeds 30 search requests per minute
THEN subsequent requests return HTTP 429 with `Retry-After` header (rate limit applied before Puppet call)

WHEN `state`, `type`, `team_id`, or `owner_id` filters are combined with a query
THEN they are translated to Puppet tag/facet filters server-side
AND `wm_<workspace_id>` is ALWAYS enforced (never user-supplied)

WHEN Puppet returns 5xx / times out
THEN the API returns HTTP 503 `SEARCH_UNAVAILABLE` (no local fallback — no FTS exists)

### SearchService (thin wrapper over PuppetClient)
- [x] [RED] 10 unit tests: happy path, zero hits, limit, workspace isolation, additional_tags enforcement, short/empty/whitespace query=ValueError, PuppetClientError→PuppetNotAvailableError (2026-04-17)
- [x] [GREEN] SearchService in application/services/search_service.py — workspace tag always injected, additional_tags prefixed with ws_tag (2026-04-17)
- [x] [GREEN] POST /api/v1/search — 401 no auth, 422 short query, 422 limit>100, 503 Puppet down (2026-04-17)
- [ ] [GREEN] GET /api/v1/search/suggest — deferred (PuppetClient has no prefix method yet)

### SavedSearchService (decision #24)
- [x] [RED] 12 unit tests: create/list (own+shared)/update/delete with ownership enforcement (2026-04-17)
- [x] [GREEN] SavedSearchService + GET/POST/PATCH/DELETE /api/v1/saved-searches + GET /{id}/run (2026-04-17)
- [x] is_shared column: migration 0100, ORM, model, mapper, repo updated (2026-04-17)

---

## Group 4 — Dashboard Services

### Acceptance Criteria — GlobalDashboardService

WHEN `GET /api/v1/dashboards/global` is called and cache is cold
THEN aggregation queries run and the result is written to Redis key `dashboard:global` with TTL 120s
AND subsequent call within TTL returns cached response without hitting the DB

WHEN any work item undergoes a state transition
THEN the `dashboard:global` Redis key is invalidated immediately

WHEN the `aging_warnings` threshold is not in env vars
THEN the system uses the default: 7 days for active states, 14 days for blocked state

WHEN `GET /api/v1/dashboards/global` is called
THEN the response includes `states: [{state, count, avg_age_days}]`, `blocked_count`, `aging_warnings`, `aging_criticals`
AND ARCHIVED items are excluded from state counts by default

WHEN an unauthenticated request is made to any dashboard endpoint
THEN the API returns HTTP 401

### GlobalDashboardService → implemented as WorkspaceDashboardService
- [x] [RED] 2 unit tests: cache invalidation, workspace-scoped cache keys (2026-04-17)
- [x] [GREEN] DashboardService.get_workspace_dashboard(): by_state, by_type, avg_completeness, 10 recent timeline events; Redis TTL 60s key dashboard:workspace:{id} (2026-04-17)
- [x] [GREEN] GET /api/v1/workspaces/dashboard — 401 no auth, 200 cached, 200 with data (2026-04-17)
- [ ] [GREEN] Cache invalidation hook in WorkItemFSMService — deferred (EP-01 agent owns that service)

### PersonDashboardService
- [x] [RED] 8 tests: happy path, zero-state, inbox counts, overload indicator (>5 in_clarification), cache hit/miss (2026-04-18)
- [x] [GREEN] PersonDashboardService.get_metrics(user_id, workspace_id): owned_by_state, pending_reviews_count, inbox_count, overloaded; cache key dashboard:person:{user_id} TTL 120s (2026-04-18)
- [x] [GREEN] GET /api/v1/dashboards/person/{user_id} route added to dashboard_controller.py (2026-04-18)

### TeamDashboardService
- [x] [RED] 6 tests: happy path, pending reviews, velocity_last_30d, blocked_count, empty team, cache hit (2026-04-18)
- [x] [GREEN] TeamDashboardService.get_metrics(team_id, workspace_id): owned_by_state, pending_reviews, velocity_last_30d, blocked_count via team_memberships subquery; cache key dashboard:team:{team_id} TTL 120s (2026-04-18)
- [x] [GREEN] GET /api/v1/dashboards/team/{team_id} route added (2026-04-18)
- [x] [REFACTOR] _require_workspace extracted in dashboard_controller.py (2026-04-18)

### Acceptance Criteria — PipelineQueryService

WHEN `GET /api/v1/pipeline` is called
THEN columns appear in canonical FSM order: draft → in_clarification → in_review → partially_validated → ready
AND ARCHIVED state is absent from columns
AND each column contains at most 20 items (ROW_NUMBER OVER PARTITION BY state)
AND items within each column are ordered by `updated_at` DESC

WHEN an item has been in its current state for more than 7 days but ≤14 days
THEN `days_in_state` value is present and the item is flaggable as amber

WHEN an item has been in its current state for more than 14 days
THEN `days_in_state` value is present and the item is flaggable as red

WHEN the `blocked` lane renders
THEN each blocked item includes `pre_block_state` (the state the item was in before being blocked)

WHEN the same filter params are requested within 30 seconds
THEN Redis cache key `pipeline:{filter_hash}` is served; no DB query is made
AND `filter_hash` is a deterministic SHA-256 of sorted filter params

WHEN an invalid filter value is supplied
THEN the API returns HTTP 422

### PipelineQueryService
- [x] [RED] 8 tests: FSM states present, archived absent, FSM order, counts, items capped at 20, blocked_lane present, cache hit, invalid filter (2026-04-18)
- [x] [GREEN] PipelineQueryService.get_pipeline(): single GROUP BY agg + capped item fetch per state; SHA-256 filter_hash cache key pipeline:{ws}:{hash} TTL 30s (2026-04-18)
- [x] [GREEN] GET /api/v1/pipeline controller + route registered in main.py (2026-04-18)

---

## Group 4b — Kanban Endpoint

Extension from: extensions.md (EP-09 / Req #6)

### API Contract

```
GET /api/v1/work-items/kanban
    ?project_id={uuid}
    &group_by=state|owner|tag|parent
    &cursor_{column_key}={opaque_cursor}   -- per-column cursor for pagination
    &limit=25                              -- cards per column per page (max 25)

Response 200:
{
  "columns": [
    {
      "key": "draft",
      "label": "Draft",
      "total_count": 42,
      "cards": [WorkItemCard],
      "next_cursor": "base64|null"
    }
  ],
  "group_by": "state"
}
WorkItemCard includes: id, title, type, state, owner_id, days_in_state, completeness,
                       tag_ids (from EP-15), attachment_count (from EP-16 denormalized column)
Errors: 401, 403, 422 (invalid group_by or limit)
```

Column ordering:
- `group_by=state`: columns in FSM order (draft → in_clarification → in_review → partially_validated → ready); ARCHIVED excluded
- `group_by=owner`: one column per distinct `owner_id` present in the project; sorted by owner display name
- `group_by=tag`: one column per tag in the project (requires EP-15); items with no tags → "Untagged" column
- `group_by=parent`: one column per distinct `parent_work_item_id` (requires EP-14 hierarchy); orphans → "No parent" column

Cards are cursor-paginated within each column (25 per column initially, independent `next_cursor` per column).

State transitions from Kanban drag-drop use the existing EP-01 transition endpoint (`POST /api/v1/work-items/{id}/transitions`). The Kanban endpoint itself is read-only.

### Acceptance Criteria — KanbanService

WHEN `GET /api/v1/work-items/kanban?group_by=state` is called
THEN columns are returned in FSM order (draft, in_clarification, in_review, partially_validated, ready)
AND ARCHIVED state is absent
AND each column includes `total_count` and up to 25 cards ordered by `updated_at DESC`
AND each card includes `tag_ids` and `attachment_count`

WHEN `GET /api/v1/work-items/kanban?group_by=owner` is called
THEN one column per distinct `owner_id` is returned, sorted by owner display name
AND items without an owner are grouped in a column with `key: "unowned"`, `label: "Unowned"`

WHEN `GET /api/v1/work-items/kanban?group_by=tag` is called
THEN one column per tag in the project is returned
AND items with no tags appear in a column with `key: "untagged"`, `label: "Untagged"`
AND items with multiple tags appear in multiple columns (duplicated — not deduplicated)

WHEN `GET /api/v1/work-items/kanban?group_by=parent` is called
THEN one column per distinct parent work item ID is returned
AND orphan items (no parent) appear in a column with `key: "no_parent"`, `label: "No parent"`

WHEN `limit=26` is supplied
THEN HTTP 422 is returned (`limit` max is 25 for Kanban)

WHEN the same request is made within 30 seconds (cache window)
THEN the response is served from Redis; no DB query executes
AND cache key is `kanban:{project_id}:{group_by}:{sorted_filter_hash}`

WHEN `group_by=invalid` is supplied
THEN HTTP 422 is returned with valid group_by options listed

- [x] [RED] 10 tests: state columns in FSM order, archived absent, cap, total_count, owner columns, unowned column, parent/no_parent, limit>25→ValueError, invalid group_by→ValueError, cache hit (2026-04-18)
- [x] [GREEN] KanbanService.get_board(): dict-keyed strategy dispatch (state/owner/tag/parent); SHA-256 cache key kanban:{ws}:{group_by}:{hash} TTL 30s (2026-04-18)
- [x] [GREEN] GET /api/v1/work-items/kanban controller + route registered in main.py (2026-04-18)
- [x] [REFACTOR] Clean strategy dispatch — no if/elif chain (2026-04-18)

---

## Group 5 — Controllers / Routes

### Acceptance Criteria

WHEN `GET /api/v1/work-items` is called without auth
THEN the API returns HTTP 401

WHEN `GET /api/v1/work-items` is called with an invalid filter value (e.g., `sort_by=nonexistent`)
THEN the API returns HTTP 422 with the list of valid sort fields

WHEN `GET /api/v1/work-items` is called with valid filters
THEN the response body matches `{ data: [WorkItemCard], pagination: {cursor, has_next, total_count}, applied_filters }` exactly

WHEN `GET /api/v1/work-items/{id}` is called for a non-existent id
THEN the API returns HTTP 404

WHEN `GET /api/v1/search` is called at 31 requests/minute by the same authenticated user
THEN the 31st request returns HTTP 429 with `Retry-After` header

WHEN `GET /api/v1/dashboards/team/{team_id}` is called with a non-existent team_id
THEN the API returns HTTP 404

WHEN `GET /api/v1/dashboards/person/{user_id}` is called with a non-existent user_id
THEN the API returns HTTP 404 (zero-item user returns 200; unknown ID returns 404)

- [x] [RED] 16 integration tests for GET /api/v1/work-items (new filters, cursor pagination, sort, auth) (2026-04-17)
- [x] [GREEN] GET /api/v1/work-items extended: project_id, creator_id, tag_id, priority, completeness_min/max, updated_after/before, sort enum, cursor, q, use_puppet (2026-04-17)
- [ ] [RED] Write integration tests for `GET /api/v1/work-items/{id}`, `/{id}/summary`, `/{id}/timeline`
- [ ] [GREEN] Implement detail, summary, timeline controllers
- [ ] [RED] Write integration tests for `GET /api/v1/search` (rate limit 30/min, filters, pagination)
- [ ] [GREEN] Implement `GET /api/v1/search` controller with rate limiting (30 req/min per user)
- [ ] [RED] Write integration tests for all four dashboard endpoints (auth, cache behavior, 404)
- [ ] [GREEN] Implement `GET /api/v1/dashboards/global`, `/person/{user_id}`, `/team/{team_id}`, `/pipeline` controllers
- [ ] All endpoints: 401 if no auth token, 403 if insufficient scope

---

## Group 6 — Performance Validation

- [ ] Run `EXPLAIN ANALYZE` on all critical queries; assert index usage in integration tests
- [ ] Load test list API with 10k items — verify P95 < 200ms
- [ ] Load test search with 50k documents — verify P95 < 400ms
- [ ] Load test dashboard endpoints — verify cache hit P95 < 150ms
- [ ] Verify no N+1 queries in any endpoint (SQLAlchemy query counting in integration tests)
- [ ] Verify all endpoints return 401 for unauthenticated requests
- [ ] Verify access scoping (user cannot access items outside their scope)
