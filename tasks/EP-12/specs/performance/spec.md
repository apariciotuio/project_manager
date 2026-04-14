# Spec: Performance — US-123

Response time targets, pagination, long-operation progress, DB query budgets, N+1 detection.

---

## Response time targets

| Endpoint category | p50 | p95 | Notes |
|-------------------|-----|-----|-------|
| Inbox list (paginated, 20 items) | <100ms | <300ms | Redis cached per user, TTL 30s |
| Element detail | <150ms | <400ms | Includes derived state computation |
| Search (full-text) | <200ms | <500ms | PostgreSQL FTS with GIN index |
| Review action submit | <300ms | <600ms | Writes audit log + FSM transition |
| Dashboard/metrics | <500ms | <1000ms | Aggregated, background-refreshed |
| File upload (per MB) | <500ms | <1500ms | Streamed to object storage |
| Long async operations | N/A | N/A | SSE progress stream (see Scenario 5) |

All targets measured at the API gateway, excluding client network latency. Targets apply to the p95 of the last 5 minutes under production load.

---

## Scenario 1 — List and search pagination

WHEN any list endpoint (inbox, elements, audit log, members) is called without pagination parameters
THEN the default page size is 20 items
AND the maximum allowed page size is 100 items
AND the response includes a `pagination` object:
  ```json
  {
    "pagination": {
      "cursor": "<opaque_base64_cursor>",
      "has_next": true,
      "total_count": 347
    }
  }
  ```

WHEN a `cursor` parameter is supplied to a list endpoint
THEN the response returns the next page of results starting after that cursor position
AND the cursor encodes: (sort_column_value, id) as a stable keyset for cursor-based pagination
AND cursor pagination is used for all lists (offset pagination is NOT used — it degrades on large tables)

WHEN `total_count` is requested for large datasets
THEN it is served from a Redis counter or approximate count (PostgreSQL `reltuples`) — not from `COUNT(*)` on each request

WHEN a search query is submitted
THEN the query uses PostgreSQL full-text search (`tsvector`/`tsquery`) with a GIN index on the relevant columns
AND search results are paginated with the same cursor pattern
AND an empty query returns the full list (paginated)

---

## Scenario 2 — DB query budget per request

WHEN any API endpoint processes a request
THEN the total number of SQL queries is <=5 for simple read endpoints (detail, single-entity operations)
AND <=10 for complex read endpoints (list with filters, dashboard)
AND <=3 for write endpoints (create, update, status transition)

WHEN a query budget is exceeded in development or staging
THEN a WARNING log is emitted with: endpoint, query_count, queries (as list), correlation_id
AND the development environment uses SQLAlchemy event listeners to count and log all queries per request

WHEN an N+1 pattern is detected (same query executed N times with different IDs in a loop)
THEN it is treated as a MUST FIX — not a should-fix
AND the fix is to use a JOIN or `IN` clause to batch the queries

---

## Scenario 3 — Redis caching strategy

WHEN the inbox list is requested for a user
THEN the result is cached in Redis with key `inbox:{user_id}:{workspace_id}` and TTL 30 seconds
AND on any element status change affecting that user's inbox, the cache key is invalidated immediately (not on next read)

WHEN an element detail is requested
THEN the response is NOT cached in Redis (detail pages require fresh derived state from the FSM)
AND computed/aggregated fields (e.g., comment count, attachment count) are cached with TTL 60 seconds with key `element:agg:{element_id}`

WHEN the dashboard metrics endpoint is called
THEN the aggregated result is cached in Redis with key `dashboard:{workspace_id}` and TTL 120 seconds
AND a background Celery task refreshes the cache proactively every 90 seconds

WHEN Redis is unavailable
THEN the application falls back to direct DB queries with a WARNING log
AND no 5xx is returned to the client due to cache unavailability alone

---

## Scenario 4 — Database index requirements

WHEN a query filters by `workspace_id` on any tenant-scoped table
THEN a composite index exists: `(workspace_id, <primary_sort_column>)` e.g., `(workspace_id, created_at DESC)`

WHEN a query filters by `assignee_id`, `status`, or `element_type`
THEN a partial or regular index exists for each high-cardinality filter column

WHEN a full-text search column is used
THEN a GIN index exists on the `tsvector` computed column

WHEN a foreign key is declared
THEN a supporting index exists on the FK column in the referencing table (PostgreSQL does not auto-create these)

WHEN a new migration is added that introduces a table scan on an existing large table
THEN the migration is blocked in CI with a note to add the required index first

---

## Scenario 5 — Long-operation progress reporting

WHEN a user triggers a long-running operation (bulk import, report generation, Jira sync >10 elements)
THEN the API returns HTTP 202 Accepted immediately with body:
  ```json
  { "job_id": "<uuid>", "status": "queued", "progress_url": "/api/v1/jobs/{job_id}/progress" }
  ```

WHEN the client connects to `/api/v1/jobs/{job_id}/progress`
THEN the endpoint uses Server-Sent Events (SSE) to stream progress events
AND each event has the format:
  ```
  event: progress
  data: {"job_id": "<uuid>", "status": "running", "percent": 42, "message": "Processing item 42/100"}
  ```
AND when the job completes:
  ```
  event: complete
  data: {"job_id": "<uuid>", "status": "done", "result_url": "/api/v1/reports/{id}"}
  ```
AND when the job fails:
  ```
  event: error
  data: {"job_id": "<uuid>", "status": "failed", "error": "Human-readable message", "correlation_id": "<id>"}
  ```

WHEN the SSE connection is idle for more than 30 seconds
THEN the server sends a keepalive comment: `: keepalive\n\n`
AND the client reconnects automatically using the `Last-Event-ID` header if the connection drops

WHEN the user closes the page while a job is running
THEN the job continues in the background (Celery task is not cancelled)
AND the result is retrievable by polling `/api/v1/jobs/{job_id}` (non-SSE fallback)

---

## Scenario 6 — Frontend performance

WHEN any page is initially loaded
THEN Largest Contentful Paint (LCP) is <=2.5 seconds on a simulated 4G connection
AND Total Blocking Time (TBT) is <=300ms
AND Cumulative Layout Shift (CLS) is <=0.1

WHEN a route transition occurs (Next.js App Router navigation)
THEN the transition completes in <=300ms for cached routes
AND skeleton loaders are shown immediately (no blank flash)

WHEN a list view has >100 items visible in the DOM
THEN virtual rendering (windowing) is used to keep rendered nodes <=50 at a time
AND scroll performance stays at 60fps on mid-range mobile hardware

WHEN images are loaded
THEN `next/image` with lazy loading and explicit `width`/`height` is used on all images
AND avatar images are served at 2x their display size for retina screens

---

## Scenario 7 — Graceful degradation

WHEN PostgreSQL read latency exceeds 1000ms on a single query
THEN the request returns HTTP 503 with `Retry-After: 5` after the query timeout
AND the error is logged with: query plan (EXPLAIN output), duration, correlation_id

WHEN a Celery queue depth exceeds 500 pending tasks
THEN new task submissions return a warning in the 202 response: `"queue_depth_warning": true`
AND the operations team is alerted via the monitoring dashboard

WHEN a third-party integration (Jira) is unavailable
THEN dependent features degrade gracefully: sync operations queue for retry (EP-03 queues)
AND the UI shows "Jira sync unavailable — retrying" rather than an error
AND no unhandled exception propagates to the user

---

## Scenario 8 — Performance testing gate in CI

WHEN a PR modifies any endpoint handler, service, or repository method
THEN the CI pipeline runs a lightweight load test (Locust or k6) against that endpoint with 10 concurrent users
AND the test fails the pipeline if p95 latency exceeds the target from the table above

WHEN a migration is added
THEN the CI runs `EXPLAIN ANALYZE` on the 3 most common queries for that table
AND the pipeline fails if a sequential scan is detected on a table with >10,000 expected rows
