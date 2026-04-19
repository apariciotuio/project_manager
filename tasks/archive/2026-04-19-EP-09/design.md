# Technical Design: EP-09 — Listings, Dashboards, Search & Workspace

**Date**: 2026-04-13
**Status**: Proposed

> **⚠️ SUPERSEDES (2026-04-14, post-EP-18)**: the Puppet contract described in §Search sections was drafted before Puppet's real OpenAPI was known. Workspace isolation on every Puppet call now uses `category: "tuio-wmp:ws:<workspace_id>:workitem|section|comment"` (NOT the `wm_<workspace_id>` tag). Entity facets (state, type, owner, team, archived, user-tag slugs) remain as `tags`. Authoritative definition in `tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md#semantic-search` and `tasks/EP-13/design.md` supersede notice. All prose below that references `wm_<workspace_id>` is legacy; the implementation follows the category+tags split above.

---

## 1. List API Design

### Endpoint

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
```

### Cursor-Based Pagination

Offset pagination breaks under concurrent writes. Cursor is the correct choice.

Cursor encodes `(sort_value, id)` as base64 JSON. For `sort_by=updated_at`:
```json
{"updated_at": "2026-04-10T14:32:00Z", "id": "uuid-here"}
```

SQL keyset predicate:
```sql
WHERE (updated_at, id) < (:last_updated_at, :last_id)
ORDER BY updated_at DESC, id DESC
LIMIT :limit + 1
```

If `limit + 1` rows returned, there is a next page — return cursor for row `limit`, strip it from results.

### Filter Parameters

| Parameter | Type | SQL Condition |
|-----------|------|---------------|
| `state` | `[]enum` | `state = ANY(:states)` |
| `owner_id` | `uuid \| "me"` | `owner_id = :resolved_user_id` |
| `type` | `[]enum` | `type = ANY(:types)` |
| `team_id` | `uuid \| "mine"` | `team_id = :team_id` or `team_id = ANY(:my_team_ids)` |
| `project` | `string` | `LOWER(project) = LOWER(:project)` |
| `include_archived` | `bool` | omit `state != 'archived'` exclusion if true |

All filters AND-combined. Multi-value params OR-combined within the filter.

### Required Indexes

```sql
CREATE INDEX idx_work_items_state_updated ON work_items (state, updated_at DESC);
CREATE INDEX idx_work_items_owner_updated ON work_items (owner_id, updated_at DESC);
CREATE INDEX idx_work_items_team_updated ON work_items (team_id, updated_at DESC);
-- Composite for common combined filter:
CREATE INDEX idx_work_items_state_owner ON work_items (state, owner_id, updated_at DESC);
```

### Sort Options

Supported: `updated_at` (default), `created_at`, `title`, `state`, `completeness`.
`title` and `state` sorts use `NULLS LAST`. `completeness` is a derived column — store as materialized column or compute inline (simple enough at current scale).

### Response Shape

```json
{
  "data": [...],
  "pagination": {
    "cursor": "base64...",
    "has_next": true,
    "total_count": 142
  },
  "applied_filters": {
    "state": ["draft", "in_clarification"],
    "owner_id": "uuid-resolved"
  }
}
```

`total_count` requires a `COUNT(*)` with same WHERE clause. Run as separate query — acceptable at current scale. If count queries become slow at scale, switch to estimated counts via `pg_stats`. ⚠️ originally MVP-scoped — see decisions_pending.md

---

## 2. Dashboard Aggregation: Materialized Views vs On-Demand + Redis Cache

**Decision: On-demand SQL queries + Redis cache (TTL 120s). No materialized views.** ⚠️ originally MVP-scoped — see decisions_pending.md

Materialized views require `REFRESH MATERIALIZED VIEW` (full recompute or CONCURRENTLY), add operational complexity (refresh scheduling or trigger-based refresh), and provide no latency advantage when Redis is in front. They also don't support per-user/per-team scoping without multiple views.

Redis cache with targeted invalidation on state-change events is simpler, cheaper to operate, and good enough for the expected load profile.

### Cache Key Strategy

Cache TTL policy is owned by EP-12. Dashboard TTL is 120s; pipeline TTL is 30s (higher churn tolerance).

| Dashboard | Cache Key | TTL | Invalidation Trigger |
|-----------|-----------|-----|----------------------|
| Global | `dashboard:global` | 120s | Any work_item state change |
| By Person | `dashboard:person:{user_id}` | 120s | State change where owner_id = user_id |
| By Team | `dashboard:team:{team_id}` | 120s | State change where team_id = team_id |
| Pipeline | `pipeline:{filter_hash}` | 30s | Any state change (broad invalidation acceptable) |

Invalidation is event-driven: the service layer publishes a cache invalidation event after any work_item mutation. A Celery task (or synchronous Redis DELETE in the service layer) clears the affected keys.

### Aggregation Query (Global Example)

```sql
SELECT
  state,
  COUNT(*) AS count,
  AVG(EXTRACT(EPOCH FROM (NOW() - state_entered_at)) / 86400) AS avg_age_days
FROM work_items
WHERE state != 'archived'
GROUP BY state;
```

`state_entered_at` is a column updated by the FSM on each state transition (EP-01 should provide this — if not, derive from the last transition event in history table).

### Aging Thresholds

Configurable via environment variable, defaulting to:
- `AGING_WARNING_DAYS=7`
- `AGING_CRITICAL_DAYS=14`

Applied at the query/response layer, not hardcoded in SQL.

---

## 3. Pipeline View: Query Design

```sql
SELECT
  state,
  COUNT(*) AS count,
  AVG(EXTRACT(EPOCH FROM (NOW() - state_entered_at)) / 86400) AS avg_age_days,
  json_agg(
    json_build_object(
      'id', id, 'title', title, 'type', type,
      'owner_id', owner_id, 'completeness', completeness,
      'days_in_state', EXTRACT(EPOCH FROM (NOW() - state_entered_at)) / 86400
    )
    ORDER BY updated_at DESC
  ) FILTER (WHERE rn <= 20) AS items
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY state ORDER BY updated_at DESC) AS rn
  FROM work_items
  WHERE state != 'archived'
  -- AND filters applied here
) sub
GROUP BY state;
```

This returns column summaries and the first 20 cards per column in a single query. At current target scale (< 5000 items), this runs comfortably under 100ms.

For the blocked lane, a separate query fetches blocked items with their pre-block state from the history table.

---

## 4. Search: delegated to Puppet RAG (EP-13)

**Decision (resolution #4, #9, #24, #28): search is fully delegated to Puppet.** No PostgreSQL FTS. No `tsvector` column. No `aggregated_*_text` denormalized columns. No GIN search index. No Elasticsearch. No RRF hybrid. No per-workspace embeddings. No learned re-ranker. No multi-language.

The product UI calls `PuppetClient.search(query, tags, limit, cursor)` directly from the backend. Puppet returns ranked `document_id`s (work-item IDs, comment IDs, timeline entry IDs) plus snippets. The backend then fetches the full rows by ID for rendering.

- Tag filter on every query: `wm_<workspace_id>` plus optional sub-tags (`wm_type_bug`, `wm_project_<id>`, `wm_tag_<slug>`).
- Prefix / type-ahead: `PuppetClient.search_prefix(prefix, tags)`.
- Faceted filters: type, state, project, team, owner, tags — applied server-side by Puppet using the document metadata.
- Saved searches: `saved_searches(id, user_id, workspace_id, name, query_params JSONB, created_at)` — stored on our side; query params are replayed through `PuppetClient`.
- Eventual consistency target: <3s from write to search visibility.
- If Puppet is unavailable: the searchbar shows "search unavailable" but CRUD + filter listings remain fully functional (they go straight to Postgres).

See EP-13 for the push-on-write sync pipeline, the `PuppetClient` API, health check, and document schema.

---

## 5. Unified Detail View: Single Call vs Composite

**Decision: Single API call that assembles the full payload server-side.**

Composite (BFF-style multiple calls from frontend) means: N round trips, waterfall loading, complex frontend state management, and harder error handling. For a detail view where ALL sections are needed immediately, this is the wrong trade-off.

The server-side assembly uses a single async SQLAlchemy query with `selectinload` for relationships. Timeline is the exception — it is loaded lazily (separate call on scroll/expand) because it can be large.

```
GET /api/v1/work-items/{id}
→ returns: header + spec + tasks + validation_checklist + reviews + comments

GET /api/v1/work-items/{id}/timeline
→ lazy-loaded: state transitions, ownership changes, review events
→ paginated (cursor-based, 50 events per page)

GET /api/v1/work-items/{id}/summary
→ quick view payload: excerpt only, no full content
```

### Server-Side Assembly Query

```python
await session.execute(
    select(WorkItem)
    .options(
        selectinload(WorkItem.tasks),
        selectinload(WorkItem.validation_requirements),
        selectinload(WorkItem.review_requests).selectinload(ReviewRequest.responses),
        selectinload(WorkItem.comments).selectinload(Comment.author),
    )
    .where(WorkItem.id == item_id)
)
```

This fires 5 SQL queries total (SQLAlchemy selectinload pattern — not N+1).

---

## 6. Frontend Component Architecture

```
app/
  work-items/
    page.tsx                    -- list page (server component, initial data fetch)
    [id]/
      page.tsx                  -- detail page (server component)
      loading.tsx               -- skeleton
  dashboards/
    global/page.tsx
    person/[userId]/page.tsx
    team/[teamId]/page.tsx
    pipeline/page.tsx

components/
  work-items/
    WorkItemList.tsx            -- client component, handles filter state
    WorkItemCard.tsx            -- card for list and pipeline
    QuickViewPanel.tsx          -- slide-over panel, client component
    FilterBar.tsx               -- filter controls, client component
    SortControl.tsx
  detail/
    WorkItemDetail.tsx          -- assembles all sections
    HeaderSection.tsx
    SpecSection.tsx
    TasksSection.tsx
    ValidationSection.tsx
    ReviewsSection.tsx
    CommentsSection.tsx
    TimelineSection.tsx         -- lazy, loaded on expand
  dashboards/
    StateBucketWidget.tsx
    AgingWidget.tsx
    BlockedItemsWidget.tsx
    ReviewActivityWidget.tsx
    TeamVelocityWidget.tsx
  pipeline/
    PipelineBoard.tsx           -- column layout
    PipelineColumn.tsx          -- single state column
    PipelineCard.tsx            -- item card in pipeline
    BlockedLane.tsx
  search/
    SearchBar.tsx               -- controlled input, debounced 300ms
    SearchResults.tsx
    SearchResultCard.tsx        -- with highlight rendering
```

**State management**: URL search params as source of truth for all filters and search query (`useSearchParams` / `useRouter`). No global state store needed. React Query (`@tanstack/react-query`) for data fetching, caching, and background refresh.

**Dashboard refresh**: React Query `staleTime: 55_000` + `refetchInterval: 300_000` (5 min polling). Manual refresh button calls `queryClient.invalidateQueries`.

---

## 7. Performance Budget

| Endpoint | Target P50 | Target P95 | Notes |
|----------|-----------|-----------|-------|
| `GET /api/v1/work-items` (list) | < 80ms | < 200ms | With indexes, cursor pagination |
| `GET /api/v1/work-items/{id}` (detail) | < 120ms | < 300ms | selectinload pattern |
| `GET /api/v1/work-items/{id}/summary` | < 50ms | < 100ms | Minimal projection |
| `GET /api/v1/search` | < 200ms | < 400ms | GIN index on tsvector |
| `GET /api/v1/dashboards/global` | < 50ms | < 150ms | Redis cache hit; cold: < 500ms |
| `GET /api/v1/dashboards/person/{id}` | < 50ms | < 150ms | Redis cache hit |
| `GET /api/v1/dashboards/team/{id}` | < 50ms | < 150ms | Redis cache hit |
| `GET /api/v1/pipeline` | < 80ms | < 200ms | Redis cache hit; cold: < 300ms |
| `GET /api/v1/work-items/{id}/timeline` | < 100ms | < 250ms | Paginated, indexed by item_id + created_at |

All targets measured at the application layer (excluding network RTT). PostgreSQL connection pool: min 5, max 20. Redis connection pool: min 2, max 10.

---

## 8. API Route Summary

```
GET  /api/v1/work-items                        -- list with filters
GET  /api/v1/work-items/{id}                   -- unified detail
GET  /api/v1/work-items/{id}/summary           -- quick view
GET  /api/v1/work-items/{id}/timeline          -- lazy history
GET  /api/v1/search                            -- full-text search
GET  /api/v1/dashboards/global                 -- global dashboard
GET  /api/v1/dashboards/person/{user_id}       -- by-person dashboard
GET  /api/v1/dashboards/team/{team_id}         -- by-team dashboard
GET  /api/v1/pipeline                          -- pipeline view
```

All endpoints under `/api/v1/`. All require authentication (401 if missing, 403 if insufficient scope).

---

## 9. Kanban Board View

Extension from: extensions.md (EP-09 / Req #6)

### Endpoint

```
GET /api/v1/work-items/kanban
    ?project_id={uuid}
    &group_by=state|owner|tag|parent
    &cursor_{column_key}={opaque_cursor}
    &limit=25
```

### Response Shape

```json
{
  "columns": [
    {
      "key": "draft",
      "label": "Draft",
      "total_count": 42,
      "cards": [
        {
          "id": "...", "title": "...", "type": "story",
          "state": "draft", "owner_id": "...",
          "days_in_state": 3, "completeness": 0.6,
          "tag_ids": ["uuid1", "uuid2"],
          "attachment_count": 2
        }
      ],
      "pagination": { "cursor": "base64string|null", "has_next": false }
    }
  ],
  "group_by": "state"
}
```

Cards are cursor-paginated within each column (25 per column per page, independent `{cursor, has_next}` per column — canonical EP-12 shape). The `limit` param applies per-column; max 25.

### Group-by Modes

| `group_by` | Column definition | Special columns |
|------------|-------------------|-----------------|
| `state` (default) | One column per FSM state (EP-01 canonical enum); soft-deleted items excluded; columns ordered by FSM transition order | — |
| `owner` | One column per distinct `owner_id` in project; sorted by owner display name | `key: "unowned"` for items without owner |
| `tag` | One column per tag in project (EP-15 required); items with multiple tags appear in multiple columns | `key: "untagged"` for items with no tags |
| `parent` | One column per distinct `parent_work_item_id` (EP-14 required) | `key: "no_parent"` for orphan items |

`tag` and `parent` groupings are available as soon as EP-15 and EP-14 are implemented; the endpoint returns HTTP 422 with `error.code: dependency_not_available` if the required epic tables are absent at query time.

### Drag-and-Drop Semantics

The Kanban endpoint itself is **read-only**. State changes via card drag-drop use the existing EP-01 state transition endpoint:

```
POST /api/v1/work-items/{id}/transitions
Body: { "to_state": "in_clarification" }
```

Transition validation gates (EP-01) apply. If a gate fails, the response is HTTP 422 with a validation message — the frontend reverts the card with an inline error toast and bounce animation.

Drag-and-drop is only semantically meaningful for `group_by=state`. Other `group_by` modes render the board read-only (no transition called on drop).

### Caching

Redis cache key: `kanban:{project_id}:{group_by}:{sha256(sorted_filter_params)}`, TTL 30s.

Cache is invalidated on any work item state change in the project (same broad invalidation strategy as pipeline cache — acceptable for a 30s TTL).

### Frontend Library Choice

`@dnd-kit/core` + `@dnd-kit/sortable` — lightweight, no HTML5 drag backend dependency, accessibility-first, works with touch events (mobile swipe does not trigger accidental drags, mobile tap navigates to detail page instead).

Rejected: `react-dnd` — requires HTML5 backend, heavier, less accessible.

### Mobile Behavior

No drag-and-drop on mobile. Horizontal scroll between columns with `scroll-snap-type: x mandatory`. Tapping a card navigates to full detail page. Columns are min-width `85vw` to give clear snap boundaries.

---

## 10. Rejected Alternatives (pre-extension)

| Decision | Rejected Alternative | Reason |
|----------|---------------------|--------|
| Redis cache + on-demand queries | PostgreSQL materialized views | No per-user scoping; refresh scheduling complexity; no latency benefit with Redis in front |
| PG native FTS | Elasticsearch | Operational overhead unjustified at current target scale; PG FTS sufficient for < 100k docs ⚠️ originally MVP-scoped — see decisions_pending.md |
| Single API call for detail | BFF composite fetch | Multiple round trips; waterfall loading; complex error handling |
| Cursor pagination | Offset pagination | Breaks under concurrent writes; no stable position under inserts |
| URL params as filter state | Redux/Zustand global store | Bookmarkable URLs; no extra dependency; works with SSR |
