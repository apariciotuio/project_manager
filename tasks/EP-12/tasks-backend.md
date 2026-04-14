# EP-12 Backend Subtasks — Responsive, Security, Performance

> **Propagation note (2026-04-14, decisions_pending.md #27)**: Observability is **deferred**. All Sentry, Prometheus, OpenTelemetry, Loki, health-dashboard, trace-sampling, LLM-metrics, and `product_events` tasks below are **obsolete**. Keep only stdlib logging + `CorrelationIDMiddleware`. Re-plan this file at TDD time.

**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery
**Note**: EP-12 must be implemented FIRST. All other epics depend on this middleware stack.

---

## API Contract (new endpoints introduced by EP-12)

```
GET  /api/v1/jobs/{job_id}/progress    -- SSE stream for long-running Celery jobs
     Auth: authenticated member owning the job
     Content-Type: text/event-stream
     SSE frame: data: {"type": "<event_type>", "payload": {...}, "channel": "<channel>"}
     event: done
     data: {"message_id": "uuid"}
     Keepalive: ": keepalive" comment every 30s
     Errors: 401, 404 (job not found)

POST /api/v1/csp-report               -- CSP violation reports (no-auth, log at WARN)
     Body: CSP report JSON
     Response: 204

GET  /api/v1/ops/queue-depths          -- ops only (requires ops capability)
     Response 200: { "queues": [{ "name", "depth", "consumers" }] }

GET  /api/v1/ops/integration-health    -- ops only
     Response 200: { "integrations": [{ "id", "type", "state", "error_streak" }] }
```

### Middleware chain (all requests)
```
CorrelationIDMiddleware  → X-Correlation-ID header in/out
RequestLoggingMiddleware → structured log per request
CORSMiddleware           → ALLOWED_ORIGINS allowlist
RateLimitMiddleware      → Redis sliding window (10/min unauth, 300/min auth)
JWTAuthMiddleware        → validate token, attach user to request.state
(per-endpoint) require_capabilities([...])
InputValidationMiddleware → Pydantic, handled by FastAPI
```

---

## Group 1 — Foundation: Middleware Stack (do this first)

### Acceptance Criteria — Middleware Ordering & Correlation ID

WHEN a request arrives with no `X-Correlation-ID` header
THEN the middleware generates a UUID v4 and adds it to the response as `X-Correlation-ID`
AND structlog binds `correlation_id` for the entire request context

WHEN a request arrives with a valid UUID in `X-Correlation-ID`
THEN that value is passed through unchanged to the response header
AND all log lines for the request include that UUID as `correlation_id`

WHEN `X-Correlation-ID` header contains a non-UUID string
THEN the middleware discards it, generates a new UUID v4, and proceeds

WHEN the middleware chain processes a request
THEN the order is: CorrelationID → RequestLogging → CORS → RateLimit → JWTAuth → per-endpoint `require_capabilities` → InputValidation → handler
AND no handler executes before all earlier middleware passes

WHEN a request completes (any status code)
THEN a single structured JSON log line is emitted containing: `method`, `path`, `status_code`, `duration_ms`, `correlation_id`

WHEN any log line is emitted
THEN it is valid single-line JSON with at minimum: `timestamp`, `level`, `logger`, `message`, `correlation_id`, `environment`

### CorrelationIDMiddleware
- [ ] [RED] Test: generates UUID v4 when `X-Correlation-ID` header absent
- [ ] [RED] Test: passes through header value when valid UUID present
- [ ] [RED] Test: rejects and regenerates when header contains invalid UUID
- [ ] [RED] Test: `X-Correlation-ID` always present in response header
- [ ] [GREEN] Implement `CorrelationIDMiddleware` in `app/presentation/middleware/correlation_id.py`
- [ ] [GREEN] Bind `correlation_id` into structlog contextvars per request

### Structured Logging
- [ ] [RED] Test: log output is valid JSON with fields: `correlation_id`, `timestamp`, `level`, `logger`, `message`
- [ ] [GREEN] Configure structlog with JSON renderer and contextvars processor in `app/infrastructure/logging/setup.py`
- [ ] [GREEN] Import and initialize in `app/main.py`

### RequestLoggingMiddleware
- [ ] [RED] Test: logs `method`, `path`, `status_code`, `duration_ms` after each request
- [ ] [GREEN] Implement `RequestLoggingMiddleware` in `app/presentation/middleware/request_logging.py`
- [ ] [GREEN] Document middleware chain order in `app/main.py` with comments

---

## Group 2 — Security

### Capability Enforcement
- [ ] [RED] Test: `require_capabilities(["review"])` returns 403 when member lacks capability
- [ ] [RED] Test: returns 403 when workspace_id is invalid/missing
- [ ] [RED] Test: passes through when member has required capability
- [ ] [RED] Test: superadmin bypass is explicit and logs the bypass
- [ ] [GREEN] Implement `require_capabilities` FastAPI dependency in `app/presentation/dependencies/auth.py`
- [ ] [REFACTOR] Scan all existing protected endpoints across other epics and apply `require_capabilities`

### Acceptance Criteria — CORS

WHEN a browser sends a cross-origin request from an origin in `ALLOWED_ORIGINS`
THEN the response includes the correct `Access-Control-Allow-Origin` header matching that origin

WHEN a browser sends a cross-origin request from an origin NOT in `ALLOWED_ORIGINS`
THEN the response does NOT include `Access-Control-Allow-Origin`
AND `Access-Control-Allow-Origin: *` is NEVER set in any non-development environment

WHEN `ALLOWED_ORIGINS` is empty and the environment is not `development`
THEN the application refuses to start and logs: "ConfigurationError: ALLOWED_ORIGINS is required in non-dev environments"

WHEN a CORS preflight OPTIONS request is received
THEN the response includes `Access-Control-Max-Age: 600`

### CORS
- [ ] [RED] Test: CORS middleware rejects origin not in `ALLOWED_ORIGINS`
- [ ] [RED] Test: app startup raises `ConfigurationError` when `ALLOWED_ORIGINS` is empty in non-dev env
- [ ] [GREEN] Configure `CORSMiddleware` with `ALLOWED_ORIGINS` allowlist from env
- [ ] [GREEN] Add startup validation for `ALLOWED_ORIGINS` in settings

### Acceptance Criteria — Rate Limiting

WHEN an unauthenticated caller sends 11 requests/minute to any unauthenticated endpoint
THEN the 11th request returns HTTP 429 with `Retry-After` header
AND the event is logged with: `ip_address`, `endpoint`, `request_count`, `window`

WHEN an authenticated user sends 301 requests/minute
THEN the 301st request returns HTTP 429

WHEN any request is processed (regardless of rate limit outcome)
THEN the response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers
AND the sliding window uses Redis key `ratelimit:{identifier}:{window_start_minute}` with INCR + EXPIRE

WHEN Redis is unavailable
THEN rate limiting is bypassed (fail-open for availability) and a WARNING is logged
AND no 5xx is returned to the client due to rate limiter failure alone

### Rate Limiting
- [ ] [RED] Test: unauthenticated endpoint returns 429 after 10 req/min from same IP; response includes `Retry-After` header
- [ ] [RED] Test: authenticated endpoint returns 429 after 300 req/min from same user
- [ ] [RED] Test: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers present on all responses
- [ ] [GREEN] Implement `RateLimitMiddleware` in `app/infrastructure/rate_limiting/redis_rate_limiter.py` (Redis sliding window: key `ratelimit:{identifier}:{window_start_minute}`, INCR + EXPIRE)
- [ ] [GREEN] Wire into middleware chain

### Input Validation
- [ ] [RED] Test: endpoint rejects unknown fields (Pydantic `extra="forbid"`)
- [ ] [RED] Test: file upload rejected on MIME type mismatch (magic bytes check)
- [ ] [RED] Test: file upload rejected if size exceeds `MAX_UPLOAD_BYTES`
- [ ] [GREEN] Enforce `model_config = ConfigDict(extra="forbid")` on all Pydantic schemas (scan all existing schemas)
- [ ] [GREEN] Implement `FileValidator` in `app/application/validators/file_validator.py`

### CSRF
- [ ] [RED] Test: state-changing endpoint (POST/PUT/PATCH/DELETE) returns 403 on missing/invalid CSRF token
- [ ] [GREEN] Implement CSRF token middleware for state-changing methods

### Content Security Policy
- [ ] [RED] Test: all HTML responses include CSP header with required directives (default-src, script-src, etc.)
- [ ] [GREEN] Implement `/api/v1/csp-report` endpoint — logs at WARN, returns 204
- [ ] [GREEN] Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy` headers to all responses

### Audit Log Integration
- [ ] [RED] Test: login success writes audit record with required fields
- [ ] [RED] Test: 403 response writes audit record with `outcome=failure`
- [ ] [RED] Test: element status transition writes audit record
- [ ] [RED] Test: audit log write failure rolls back the originating operation (same transaction)
- [ ] [GREEN] Implement `AuditLogRepository.append()` (append-only; no update/delete) — verify aligns with EP-10 schema (no duplicate migration)
- [ ] [GREEN] Integrate audit writes at: login, token refresh, 403 handler, status transitions, credential CRUD, export

### Secrets Handling
- [ ] Grep codebase for hardcoded secrets (patterns: password, secret, key, token in non-test source)
- [ ] [GREEN] Add startup validation: if any required secret is None in production, raise `ConfigurationError` with variable name
- [ ] [GREEN] Add `scrub_sensitive_data` `before_send` hook in Sentry init to strip `Authorization` headers and credential fields

---

## Group 3 — Performance

### Acceptance Criteria — Cursor-Based Pagination

WHEN any list endpoint is called without `limit` param
THEN the default page size is 20 items

WHEN `limit=101` is supplied
THEN the API returns HTTP 422

WHEN a valid `cursor` is supplied
THEN the response returns the next page starting after the cursor position
AND the cursor encodes `(sort_column_value, id)` as a stable keyset

WHEN `total_count` is requested on a large table
THEN it is served from a Redis counter or PostgreSQL approximate count (`reltuples`) — NOT from `COUNT(*)` on each request

WHEN offset-based pagination (e.g., `?page=2&per_page=20`) is used anywhere
THEN it must be replaced with cursor-based pagination (offset pagination is a MUST FIX, not should-fix)

### Cursor-Based Pagination
- [ ] [RED] Test: list endpoint returns `pagination.cursor`, `has_next`, `total_count`
- [ ] [RED] Test: supplying cursor returns correct next page (keyset semantics)
- [ ] [RED] Test: page size defaults to 20, max 100; request above 100 returns 422
- [ ] [GREEN] Implement `PaginationCursor` dataclass with `encode()` / `decode()` in `app/domain/pagination.py`
- [ ] [GREEN] Implement `paginate()` utility for SQLAlchemy queries
- [ ] [GREEN] Apply to: inbox list, work item list, member list, audit log list, search results
- [ ] [REFACTOR] Eliminate any offset-based pagination from existing endpoints

### Acceptance Criteria — Redis Caching

WHEN the inbox list is requested and cache is warm
THEN no SQLAlchemy DB query is executed (assert via query counter in tests)

WHEN any element status change affects a user's inbox
THEN the `inbox:{user_id}:{workspace_id}` key is invalidated before the HTTP response returns (synchronous invalidation)

WHEN Redis is unavailable
THEN `CacheService` falls back to direct DB queries
AND a WARNING log is emitted
AND no HTTP 5xx is returned to the client

Cache key strategy (non-negotiable — must match exactly):
- Inbox: `inbox:{user_id}:{workspace_id}` TTL 30s
- Work item aggregates: `work_item:agg:{work_item_id}` TTL 60s
- Dashboard: `dashboard:{workspace_id}` TTL 120s
- Search: `search:{workspace_id}:{hash(query)}` TTL 15s

### Redis Caching
- [ ] [RED] Test: inbox list cache hit avoids DB query (assert no DB call when cache warm)
- [ ] [RED] Test: inbox cache invalidated on element status change affecting assignee
- [ ] [RED] Test: Redis unavailable falls back to DB without raising 5xx
- [ ] [GREEN] Implement `CacheService` in `app/infrastructure/cache/redis_cache.py` — cache-aside pattern
- [ ] [GREEN] Apply cache key strategy per design.md table: `inbox:{user_id}:{workspace_id}` (TTL 30s), `work_item:agg:{work_item_id}` (TTL 60s), `dashboard:{workspace_id}` (TTL 120s), `search:{workspace_id}:{hash(query)}` (TTL 15s)

### N+1 Detection
- [ ] [GREEN] Implement `QueryCounterMiddleware` in `app/infrastructure/db/query_counter.py` — SQLAlchemy `before_cursor_execute` event listener; contextvars counter
- [ ] [GREEN] Emit WARNING log when query count exceeds budget per endpoint (dev + staging only; off in production)
- [ ] Run existing endpoints with middleware enabled; fix any N+1 found

### DB Index Audit
- [ ] Audit existing migrations for missing composite indexes on `(workspace_id, created_at DESC)`
- [ ] Audit FK columns for missing supporting indexes
- [ ] Create migration for any missing indexes
- [ ] Document in project CLAUDE.md: all new migrations must include EXPLAIN ANALYZE output for 3 most frequent queries

### Acceptance Criteria — SSE Infrastructure

WHEN a client connects to `GET /api/v1/jobs/{job_id}/progress`
THEN the response `Content-Type` is `text/event-stream`
AND each event frame is: `data: {"type": "...", "payload": {...}, "channel": "..."}\n\n`

WHEN the Celery task completes successfully
THEN a frame with `event: done` is sent: `data: {"message_id": "uuid"}\n\n`
AND the SSE generator closes cleanly

WHEN the Celery task fails
THEN a frame with `event: error` is sent with the error message
AND the generator closes cleanly

WHEN the SSE connection is idle for 30 seconds
THEN the server sends `: keepalive\n\n` to prevent connection timeout

WHEN the client disconnects mid-stream
THEN the generator detects the disconnect via `asyncio.CancelledError`
AND the Redis subscription is unsubscribed immediately (no resource leak)

WHEN `GET /api/v1/jobs/{job_id}/progress` is called for a job_id not owned by the requesting user
THEN the API returns HTTP 404

WHEN `GET /api/v1/jobs/{job_id}/progress` is called without authentication
THEN the API returns HTTP 401

WHEN EP-03 or EP-08 emits SSE events
THEN they delegate to `SseHandler.stream(channel, request)` — no independent SSE implementations exist

### Long-Operation SSE Infrastructure
- [ ] [RED] Test: `GET /api/v1/jobs/{job_id}/progress` streams SSE events with correct format (`data: {...}` frames)
- [ ] [RED] Test: `event: done` frame sent when Celery task finishes
- [ ] [RED] Test: `event: error` frame sent when Celery task fails
- [ ] [RED] Test: `: keepalive` comment sent every 30s on idle connection
- [ ] [RED] Test: client disconnect triggers Redis unsubscribe and generator cleanup
- [ ] [GREEN] Implement `RedisPubSub` in `infrastructure/sse/redis_pubsub.py` — `publish(channel, message)`, `subscribe(channel) -> AsyncIterator[dict]`
- [ ] [GREEN] Implement `SseHandler` in `infrastructure/sse/sse_handler.py` — `StreamingResponse` wrapper; reads from Redis channel; formats SSE frames; handles disconnect
- [ ] [GREEN] Implement `ChannelRegistry` in `infrastructure/sse/channel_registry.py` — maps channel names to Redis key patterns
- [ ] [GREEN] Implement `JobProgressService` — reads/writes job state in Redis
- [ ] [GREEN] Implement SSE endpoint `GET /api/v1/jobs/{job_id}/progress`
- [ ] [GREEN] Implement Celery task base class that updates Redis job state on progress/complete/fail

**Channel naming**:
- Conversation streaming (EP-03): `sse:thread:{thread_id}`
- User notifications (EP-08): `sse:user:{user_id}`

Both EP-03 and EP-08 must delegate to `SseHandler.stream(channel, request)` — no independent SSE implementations.

---

## Group 4 — Observability

### Acceptance Criteria — Sentry & Observability

WHEN an unhandled exception occurs
THEN `sentry_sdk.capture_exception()` is called automatically
AND the Sentry event includes `correlation_id` tag and `user_id`, `workspace_id` as context

WHEN `scrub_sensitive_data` before_send hook runs
THEN `Authorization` headers and any key matching `credentials`, `token`, `secret`, `password` are stripped from Sentry breadcrumbs

WHEN `ProductEventService.track(event)` is called and the analytics backend is unavailable
THEN no exception propagates to the caller
AND a WARN log is emitted with the event name and `correlation_id`

WHEN `GET /api/v1/ops/queue-depths` is called without the `ops` capability
THEN the API returns HTTP 403

WHEN Jira returns HTTP 401 during sync
THEN an `integration.failed` product event is emitted
AND the workspace admin receives an SSE notification
AND `jira_config.state` is set to `credential_error` (transition to error after 3 consecutive failures per EP-10 rules)

### Sentry Backend
- [ ] [GREEN] Add `sentry-sdk` to dependencies (Python)
- [ ] [GREEN] Initialize Sentry in `app/main.py` with `FastApiIntegration`, `SqlalchemyIntegration`, `CeleryIntegration`; `traces_sample_rate=0.1`
- [ ] [GREEN] Add `scrub_sensitive_data` before_send hook
- [ ] [GREEN] Inject `correlation_id` and `user_id` as Sentry tags in `CorrelationIDMiddleware`
- [ ] [RED] Test: unhandled exception is captured (mock Sentry client, verify `capture_exception` called)
- [ ] [RED] Test: handled integration failure calls `capture_exception` with `correlation_id` extra

### Product Event Service
- [ ] [RED] Test: `ProductEventService.track()` calls backend with correct event schema
- [ ] [RED] Test: backend unavailability does NOT propagate exception — logs warning only
- [ ] [GREEN] Implement `ProductEventService` and `ProductEventBackend` interface in `app/application/services/product_event_service.py`
- [ ] [GREEN] Implement Postgres-backed backend: append-only `product_events` table ⚠️ originally MVP-scoped — see decisions_pending.md
- [ ] [GREEN] Emit events at: login, element created/submitted/reviewed/exported, search performed, integration sync/fail, member invite/remove

### Integration Failure Visibility
- [ ] [RED] Test: Jira 401 marks integration as `credential_error`, emits `integration.failed` product event, sends SSE notification to workspace admin
- [ ] [RED] Test: admin dashboard integration health reflects failure streak
- [ ] [GREEN] Implement `integration_sync_log` table and repository (verify alignment with EP-10 `jira_sync_logs` — no duplicate migration)
- [ ] [GREEN] Write integration failure banner query for dashboard

### Ops Dashboard Endpoints
- [ ] [GREEN] Create DB view `v_endpoint_metrics` from request log table (requires structured request logging from Group 1)
- [ ] [GREEN] Implement `GET /api/v1/ops/queue-depths` (requires ops capability; reads Celery queue depth from Redis)
- [ ] [GREEN] Implement `GET /api/v1/ops/integration-health`
