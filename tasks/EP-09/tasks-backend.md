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

- [ ] [GREEN] Migration: add `state_entered_at TIMESTAMPTZ` column to `work_items` if not present (check EP-01)
- [ ] [GREEN] Add composite indexes:
  - `(state, updated_at DESC)` on `work_items`
  - `(owner_id, updated_at DESC)` on `work_items`
  - `(team_id, updated_at DESC)` on `work_items`
  - `(state, owner_id, updated_at DESC)` on `work_items`
- [ ] [GREEN] Add index on `work_items_history(item_id, created_at DESC)` for timeline queries
- [ ] [GREEN] Migration: `saved_searches (id, workspace_id, user_id, name, query, filters JSONB, created_at, updated_at)` + index
- [ ] Do NOT add: `search_vector`, GIN index, `aggregated_comment_text`, `aggregated_task_text`, `pg_trgm` extension for FTS (decision #4 — search is Puppet-only)
- [ ] [REFACTOR] Verify all migrations are idempotent and reversible

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
- [ ] [RED] Write tests for `encode_cursor` / `decode_cursor` (valid encode/decode, tamper detection returns 422)
- [ ] [GREEN] Implement `PaginationCursor` with `encode()` / `decode()` in `domain/pagination.py` — reuse EP-12 pattern
- [ ] [GREEN] Implement `WorkItemListFilters` Pydantic model (all filter params, `extra="forbid"`, `owner_id=me` resolution)

### WorkItemListQueryBuilder
- [ ] [RED] Write unit tests: no filters, each filter individually, filter combinations, `include_archived=true`, all sort options, invalid sort=422, limit cap at 100
- [ ] [RED] Write tests for `owner_id=me` and `team_id=mine` resolution to actual UUIDs
- [ ] [GREEN] Implement `WorkItemListQueryBuilder` in `application/services/work_item_list_service.py`

### My Items Filter Extension

Support `?mine=true&mine_type=owner|creator|reviewer|any` query params on `GET /api/v1/work-items`.

Behavior when `mine=true`:
- `mine_type=owner` → `owner_id = current_user.id`
- `mine_type=creator` → `created_by = current_user.id`
- `mine_type=reviewer` → item has a pending `review_request` where `reviewer_id = current_user.id` OR `reviewer_type = 'team'` AND current user is a member of that team
- `mine_type=any` (default) → OR of all three conditions above

`mine=false` (default) → filter has no effect; all existing filters apply normally.

- [ ] [RED] Write unit tests for `WorkItemListQueryBuilder` mine filter variants:
  - `mine=true&mine_type=owner` → SQL `owner_id = :user_id`
  - `mine=true&mine_type=creator` → SQL `created_by = :user_id`
  - `mine=true&mine_type=reviewer` → subquery on `review_requests` where `reviewer_id = :user_id OR (reviewer_type='team' AND team has current user)`
  - `mine=true&mine_type=any` → OR combination of all three
  - `mine=false` → no mine condition appended; existing filters unchanged
  - `mine=true` without `mine_type` → defaults to `any`
  - `mine=true&mine_type=invalid` → HTTP 422
- [ ] [GREEN] Extend `WorkItemListFilters` Pydantic model: add `mine: bool = False`, `mine_type: Literal['owner', 'creator', 'reviewer', 'any'] = 'any'`
- [ ] [GREEN] Implement mine filter resolution in `WorkItemListQueryBuilder._apply_mine_filter()`; reviewer subquery uses `review_requests` table joined to `team_memberships` for team-type reviews
- [ ] [REFACTOR] Extract `MineFilterBuilder` pure function; test independently

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
- [ ] [RED] Write tests: basic query, prefix (decision #24), empty/short query=422, facet filters, `include_archived`, pagination, access scope enforcement (wm tag), Puppet 5xx → 503
- [ ] [GREEN] Implement `SearchService.search(query, filters, cursor, limit, user)` as a thin wrapper over `PuppetClient` from EP-13
- [ ] [GREEN] Implement `/api/v1/search/suggest` endpoint → `PuppetClient.prefix(...)`

### SavedSearchService (decision #24)
- [ ] [RED] Write tests: create / list (per user) / rename / delete; cannot access other users' saved searches
- [ ] [GREEN] Implement CRUD service + `GET/POST/PATCH/DELETE /api/v1/saved-searches`

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

### GlobalDashboardService
- [ ] [RED] Write tests: aggregation query (state counts, avg_age_days), Redis cache hit/miss, cache invalidation on state change, aging thresholds from env vars
- [ ] [GREEN] Implement `GlobalDashboardService.get_metrics()` with Redis cache (TTL 120s, key `dashboard:global`)
- [ ] [GREEN] Implement cache invalidation hook in `WorkItemFSMService` (after state transition — wire to EP-01/EP-08)

### PersonDashboardService
- [ ] [RED] Write tests: happy path, zero-state, 404 for unknown user, inbox counts on self-view, overload indicator (>5 items in in_clarification)
- [ ] [GREEN] Implement `PersonDashboardService.get_metrics(user_id, requesting_user)` (Redis cache key `dashboard:person:{user_id}`, TTL 120s)

### TeamDashboardService
- [ ] [RED] Write tests: happy path, pending reviews, velocity widget, 404, `include_sub_teams=true` recursive aggregation
- [ ] [GREEN] Implement `TeamDashboardService.get_metrics(team_id)` with optional recursive mode (Redis cache key `dashboard:team:{team_id}`, TTL 120s)
- [ ] [REFACTOR] Extract shared cache key management into `DashboardCacheService`

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
- [ ] [RED] Write tests: all states returned, counts correct, items capped at 20 per column, aging indicators (amber >7d, red >14d), blocked lane with pre-block state, filter params, Redis cache with filter_hash key
- [ ] [GREEN] Implement `PipelineQueryService.get_pipeline(filters)` using grouped query with `json_agg` and `ROW_NUMBER() OVER PARTITION BY state`
- [ ] [GREEN] Implement `filter_hash` generation (deterministic SHA-256 of sorted filter params) for Redis key `pipeline:{filter_hash}` (TTL 30s)

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

- [ ] [RED] Write unit tests for `KanbanService.get_board(project_id, group_by, cursors, limit, user)`:
  - `group_by=state`: columns in FSM order, no archived, cards capped at 25, `total_count` accurate
  - `group_by=owner`: one column per owner, unowned column present, sorted by name
  - `group_by=tag`: tag columns present, items in multiple tag columns, untagged column
  - `group_by=parent`: parent columns, no-parent column
  - per-column cursor pagination: second page returns correct next 25 cards
  - `tag_ids` and `attachment_count` present on every card
  - Redis cache hit/miss; cache TTL 30s; key includes group_by and filter hash
  - `limit > 25` → 422
  - `group_by=invalid` → 422
  - access scope: user cannot see items outside their workspace
- [ ] [GREEN] Implement `KanbanService` in `application/services/kanban_service.py`
  - `group_by=state`: single grouped query using `ROW_NUMBER() OVER (PARTITION BY state ORDER BY updated_at DESC)`, filter `rn <= limit + 1` for cursor detection, FSM order applied in Python
  - `group_by=owner|tag|parent`: separate query strategies; tag uses JOIN to `work_item_tags` (EP-15); parent uses `parent_work_item_id` (EP-14)
  - Per-column cursor: encode `(updated_at, id)` per column key; same `PaginationCursor` utility from Group 3
  - Redis cache: key `kanban:{project_id}:{group_by}:{sha256(sorted_params)}`, TTL 30s
- [ ] [GREEN] Implement `KanbanRepository` in `infrastructure/persistence/kanban_repository.py`
- [ ] [RED] Write integration tests for `GET /api/v1/work-items/kanban` (all group_by modes, pagination, auth, 422 variants)
- [ ] [GREEN] Implement `GET /api/v1/work-items/kanban` controller and route
- [ ] [REFACTOR] Ensure `group_by` strategy is a clean dispatch (dict or enum-keyed functions), not a single monolithic if/elif chain

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

- [ ] [RED] Write integration tests for `GET /api/v1/work-items` (filters, pagination, auth)
- [ ] [GREEN] Implement `GET /api/v1/work-items` controller
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
