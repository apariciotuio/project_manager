# EP-09 Backend Subtasks — Listings, Dashboards, Search & Workspace

**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery
**Depends on**: EP-12 middleware stack (correlation ID, rate limit, auth), EP-01 FSM (state_entered_at), EP-04 (versioning), EP-00 (JWT)

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
THEN `search_vector tsvector` column exists on `work_items` and is NOT NULL-able
AND GIN index `idx_work_items_search` exists on `search_vector`
AND `state_entered_at TIMESTAMPTZ` column exists on `work_items`
AND composite indexes `(state, updated_at DESC)`, `(owner_id, updated_at DESC)`, `(team_id, updated_at DESC)`, `(state, owner_id, updated_at DESC)` all exist
AND index on `work_items_history(item_id, created_at DESC)` exists

WHEN any migration is rolled back
THEN the rollback completes without error and the schema is identical to the pre-migration state

WHEN EXPLAIN ANALYZE is run on `SELECT ... WHERE state = $1 ORDER BY updated_at DESC LIMIT 25`
THEN the query plan uses an index scan, not a sequential scan

- [ ] [RED] Write test asserting `search_vector tsvector` column exists on `work_items`
- [ ] [RED] Write test asserting GIN index `idx_work_items_search` exists
- [ ] [GREEN] **Migration 0**: `CREATE EXTENSION IF NOT EXISTS pg_trgm;` — prerequisite for the GIN indexes below AND for EP-05's `gin_trgm_ops` index. Must run before any trigram/tsvector GIN index. Requires DB role with CREATE privilege (in managed PG environments the extension is typically pre-installed by ops).
- [ ] [GREEN] Migration: add `search_vector tsvector` column to `work_items`
- [ ] [GREEN] Migration: add `state_entered_at TIMESTAMPTZ` column to `work_items` if not present (check EP-01)
- [ ] [GREEN] Migration: add `aggregated_comment_text TEXT` and `aggregated_task_text TEXT` to `work_items`
- [ ] [GREEN] Create GIN index on `search_vector`
- [ ] [GREEN] Add composite indexes:
  - `(state, updated_at DESC)` on `work_items`
  - `(owner_id, updated_at DESC)` on `work_items`
  - `(team_id, updated_at DESC)` on `work_items`
  - `(state, owner_id, updated_at DESC)` on `work_items`
- [ ] [GREEN] Add index on `work_items_history(item_id, created_at DESC)` for timeline queries
- [ ] [REFACTOR] Verify all migrations are idempotent and reversible; include EXPLAIN ANALYZE on 3 queries as migration comments (EP-12 requirement)

---

## Group 2 — Search Index Maintenance

### Acceptance Criteria

WHEN a work item's title or description is updated within a transaction
THEN `search_vector` is updated before that transaction commits
AND a subsequent FTS query reflects the new content within the same test transaction

WHEN a comment is created on a work item
THEN the Celery task `reindex_work_item_search_vector` is enqueued within 1 second
AND after task execution, the comment text is searchable via FTS on the parent work item

WHEN a comment or review response is deleted
THEN the parent item's `search_vector` is re-computed excluding the deleted text
AND a search for the deleted text no longer returns the parent item (after reindex)

WHEN `build_search_vector(item_id)` is called
THEN it assigns: title=weight A, description+spec=weight B, task descriptions=weight C, comment+review text=weight D
AND the result matches `setweight(to_tsvector('english', title), 'A') || ...` composition

- [ ] [RED] Write unit tests for `tsvector` composition: title=weight A, description/spec=weight B, tasks=weight C, comments=weight D
- [ ] [GREEN] Implement SQLAlchemy `after_flush` event (or PG trigger) to update `search_vector` synchronously on title/description/spec changes
- [ ] [GREEN] Verify synchronous update completes in same transaction
- [ ] [RED] Write tests for Celery task `reindex_work_item_search_vector`
- [ ] [GREEN] Implement `reindex_work_item_search_vector` Celery task for async comment/review reindexing
- [ ] [RED] Write tests for re-computation on comment/review deletion
- [ ] [GREEN] Implement re-computation logic on deletion
- [ ] [REFACTOR] Extract `build_search_vector(item_id)` as a reusable service function

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

### Acceptance Criteria — WorkItemSearchService

WHEN a query of 2+ characters is submitted
THEN results are ranked by `ts_rank_cd` descending; secondary sort is `updated_at` descending
AND each result includes `rank`, `title_snippet`, `body_snippet` with match terms in `<mark>` tags
AND snippets are ≤200 characters per matched field

WHEN the query contains fewer than 2 characters or is empty/whitespace-only
THEN the API returns HTTP 422 with a descriptive message

WHEN the query is `"payment flow"` (double-quoted phrase)
THEN the system uses `phraseto_tsquery`; only items containing the exact phrase are returned

WHEN the query is `payment flow` (plain terms)
THEN the system uses `plainto_tsquery` (AND logic); both terms must appear

WHEN `include_archived` is not supplied (default)
THEN ARCHIVED items are excluded from results

WHEN `include_archived=true` is supplied
THEN ARCHIVED items are included

WHEN the same user exceeds 30 search requests per minute
THEN subsequent requests return HTTP 429 with `Retry-After` header

WHEN `state`, `type`, `team_id`, or `owner_id` filters are combined with a query
THEN all filters are AND-combined with the FTS match condition
AND results outside the requesting user's access scope are never returned

### WorkItemSearchService
- [ ] [RED] Write tests: basic query, phrase query (quoted → `phraseto_tsquery`), empty/short query=422, filter combinations, `include_archived`, pagination, access scope enforcement
- [ ] [GREEN] Implement `WorkItemSearchService.search(query, filters, cursor, limit, user)` using `ts_rank_cd` and `ts_headline`
- [ ] [GREEN] Implement query routing: detect quoted strings → `phraseto_tsquery`, plain → `plainto_tsquery`

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
