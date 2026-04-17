# EP-12 Backend Subtasks — Responsive, Security, Performance

> **Scope (2026-04-14, decisions_pending.md #27)**: Observability deferred. Keep stdlib `logging` + `CorrelationIDMiddleware`. Drop Sentry, Prometheus, OpenTelemetry, Loki, Grafana, trace sampling, LLM-metrics, `product_events`, integration-health endpoint, ops queue-depth endpoint, ops dashboard. Below is rewritten — obsolete sections are removed, not flagged.

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
```

### Middleware chain (all requests)
```
CorrelationIDMiddleware  → X-Correlation-ID header in/out (ContextVar bound)
RequestLoggingMiddleware → stdlib logging line per request (method, path, status, duration_ms, correlation_id)
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
AND the `correlation_id` ContextVar is set for the entire request context

WHEN a request arrives with a valid UUID in `X-Correlation-ID`
THEN that value is passed through unchanged to the response header
AND all log lines for the request include that UUID as `correlation_id`

WHEN `X-Correlation-ID` header contains a non-UUID string
THEN the middleware discards it, generates a new UUID v4, and proceeds

WHEN the middleware chain processes a request
THEN the order is: CorrelationID → RequestLogging → CORS → RateLimit → JWTAuth → per-endpoint `require_capabilities` → InputValidation → handler
AND no handler executes before all earlier middleware passes

WHEN a request completes (any status code)
THEN a single log line is emitted containing: `method`, `path`, `status_code`, `duration_ms`, `correlation_id`

### CorrelationIDMiddleware
- [ ] [RED] Test: generates UUID v4 when `X-Correlation-ID` header absent
- [ ] [RED] Test: passes through header value when valid UUID present
- [ ] [RED] Test: rejects and regenerates when header contains invalid UUID
- [ ] [RED] Test: `X-Correlation-ID` always present in response header
- [ ] [GREEN] Implement `CorrelationIDMiddleware` in `app/presentation/middleware/correlation_id.py`
- [ ] [GREEN] Bind `correlation_id` into a `ContextVar` consumed by the logging formatter

### Logging (stdlib only — decision #27)
- [ ] [RED] Test: log line includes `correlation_id` via a `Filter`/`Formatter` reading from ContextVar
- [ ] [GREEN] Configure structlog with JSON renderer and contextvars processor in `app/infrastructure/logging/setup.py`
- [ ] [GREEN] Import and initialize in `app/main.py`

### RequestLoggingMiddleware
- [x] [RED] Test: logs `method`, `path`, `status_code`, `duration_ms` after each request — 7 tests in `tests/unit/presentation/middleware/test_request_logging.py`
- [x] [GREEN] Implement `RequestLoggingMiddleware` in `app/presentation/middleware/request_logging.py` — commit 82b1e6d
- [x] [GREEN] Document middleware chain order in `app/main.py` with comments — wired in phase 9 pass (2026-04-17): RequestLoggingMiddleware, BodySizeLimitMiddleware, CORSPolicyMiddleware, SecurityHeadersMiddleware added; old CORSMiddleware removed

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
- [x] [RED] Test: CORS middleware rejects origin not in `ALLOWED_ORIGINS` — 9 tests in `tests/unit/presentation/middleware/test_cors_policy.py`
- [ ] [RED] Test: app startup raises `ConfigurationError` when `ALLOWED_ORIGINS` is empty in non-dev env — pending (settings validation)
- [x] [GREEN] Implement `CORSPolicyMiddleware` in `app/presentation/middleware/cors_policy.py` — commit 1dcddcb (wildcard-in-prod raises ValueError at startup)
- [x] [GREEN] Wire `CORSPolicyMiddleware` into `app/main.py` replacing FastAPI `CORSMiddleware` — commit 6a4d1c4 (2026-04-17)
- [ ] [GREEN] Add startup validation for `ALLOWED_ORIGINS` in settings — pending (settings layer)

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
- [x] **Settings reverted to spec defaults:** `access_token_ttl_seconds = 900` (15m) and `rate_limit_per_minute = 10` in `backend/app/config/settings.py:55,58`. DX overrides via `.env.development`. (Not a middleware implementation — just resets the config creep.)

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
- [x] [RED] Test: all HTML responses include CSP header with required directives (default-src, script-src, etc.) — 8 tests in `tests/unit/presentation/middleware/test_security_headers.py`
- [ ] [GREEN] Implement `/api/v1/csp-report` endpoint — logs at WARN, returns 204 — pending
- [x] [GREEN] Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy` headers — `app/presentation/middleware/security_headers.py` commit 1e3d5c0
- [x] [GREEN] Wire `SecurityHeadersMiddleware` into `app/main.py` — commit 6a4d1c4 (2026-04-17); `csp_overrides` reads from `settings.app.csp_overrides`

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
  - [x] **Partial:** `scripts/dev_token.py` refuses to run unless `APP_ENVIRONMENT in {development,dev,test,testing,local}` (`backend/scripts/dev_token.py:31-42`) — prevents minting arbitrary JWTs against prod DBs
- [ ] [GREEN] Logging formatter scrubs known-sensitive keys (`Authorization`, `token`, `password`, `secret`, `api_key`, `credentials`) from log records

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
- [x] [RED] Test: encode/decode round-trip, tamper rejection, empty input — 9 tests in `tests/unit/presentation/test_cursor_pagination.py`
- [ ] [RED] Test: list endpoint returns `pagination.cursor`, `has_next`, `total_count` — pending (list endpoint integration)
- [ ] [RED] Test: supplying cursor returns correct next page (keyset semantics) — pending
- [ ] [RED] Test: page size defaults to 20, max 100; request above 100 returns 422 — pending
- [x] [GREEN] Implement `encode_cursor` / `decode_cursor` in `app/presentation/pagination/cursor.py` — HMAC-signed, commit 8640c3a
- [ ] [GREEN] Implement `PaginationCursor` dataclass + `paginate()` utility for SQLAlchemy queries — pending
- [ ] [GREEN] Apply to: inbox list, work item list, member list, audit log list, search results — pending
- [ ] [REFACTOR] Eliminate any offset-based pagination from existing endpoints — pending

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
  - [x] **Partial (test/dev fake):** `InMemoryCacheAdapter` implements `ICache` with `OrderedDict` + FIFO eviction at `MAX_ENTRIES=10_000`, lazy TTL check, and a `.clear()` hook for test isolation (`backend/app/infrastructure/adapters/in_memory_cache_adapter.py`). Used when `REDIS_USE_FAKE=true`. Full Redis cache-aside path pending.
- [ ] [GREEN] Apply cache key strategy per design.md table: `inbox:{user_id}:{workspace_id}` (TTL 30s), `work_item:agg:{work_item_id}` (TTL 60s), `dashboard:{workspace_id}` (TTL 120s), `search:{workspace_id}:{hash(query)}` (TTL 15s)

### N+1 Detection
- [ ] [GREEN] Implement `QueryCounterMiddleware` in `app/infrastructure/db/query_counter.py` — SQLAlchemy `before_cursor_execute` event listener; contextvars counter
- [ ] [GREEN] Emit WARNING log when query count exceeds budget per endpoint (dev + staging only; off in production)
- [ ] Run existing endpoints with middleware enabled; fix any N+1 found

### DB Index Audit
- [ ] Audit existing migrations for missing composite indexes on `(workspace_id, created_at DESC)`
- [ ] Audit FK columns for missing supporting indexes
- [ ] Create migration for any missing indexes
  - [x] **Partial:** Migration 0032 adds partial index `idx_team_memberships_team_active ON team_memberships(team_id, joined_at) WHERE removed_at IS NULL` (`backend/migrations/versions/0032_team_memberships_idx.py`) — backs the EP-08 team-picker N+1 fix.
  - [x] **Partial:** Migration 0033 adds `workspace_id` + btree index + RLS policy to `conversation_threads`, `assistant_suggestions`, `gap_findings` (`backend/migrations/versions/0033_ep03_rls.py`) — closes EP-03 cross-workspace leakage.
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

## Group 4 — Observability (removed — decision #27)

Sentry, ProductEventService, `product_events` table, `integration_sync_log`, `v_endpoint_metrics` view, `/api/v1/ops/queue-depths`, `/api/v1/ops/integration-health`, Prometheus, Grafana, Loki, OpenTelemetry, trace sampling — **all out of scope**.

Retained:
- `CorrelationIDMiddleware` + stdlib `logging` → stdout (Group 1)
- Correlation ID on FE error UI (see `tasks.md` Group 4.1)

Integration failures are surfaced at the API boundary (error response + structured log line with `correlation_id`, `integration_id`, `error_code`). No separate `integration_sync_log`/product-event trail. Re-evaluate when scale or ops needs change.

---

## Reconciliation notes (2026-04-17)

**Opportunistic EP-12 hardening slice — no middleware stack yet.** EP-12 is the foundational middleware epic (correlation ID, rate limit, JWT, cursor pagination, Redis cache, SSE handler). None of the core middleware is implemented yet — the chain in `main.py` still runs without `CorrelationIDMiddleware`, `RequestLoggingMiddleware`, or `RateLimitMiddleware`. Today's pass fixed drift and tactical holes only.

Shipped today (all adjacent to EP-12 concerns, most outside the plan's explicit checkbox surface):

- **Config creep reverted** — `access_token_ttl_seconds` 7d → 15m; `rate_limit_per_minute` 300 → 10. DX overrides move to `.env.development` (`backend/app/config/settings.py:55,58`).
- **`assert current_user.workspace_id` → explicit `HTTPException(401, NO_WORKSPACE)`** in 16 callsites across `work_item_controller.py` + `template_controller.py`. `assert` is compiled away under `python -O` — previously these endpoints would leak `None.workspace_id` under prod build flags. Not a plan checkbox, but foundational security.
- **`dev_token.py` env guard** — refuses to mint JWTs unless `APP_ENVIRONMENT` is in `{development,dev,test,testing,local}` (`backend/scripts/dev_token.py:31-42`).
- **`InMemoryCacheAdapter`** — bounded `OrderedDict` with FIFO eviction + `.clear()` for test isolation (`backend/app/infrastructure/adapters/in_memory_cache_adapter.py`). Ships as the `REDIS_USE_FAKE` path; does NOT replace the planned Redis cache-aside service.
- **Hard `.limit(500)` on 4 list endpoints** — teams, projects, templates, workspaces/members. Stop-gap while cursor-based pagination is still un-shipped. Plan calls cursor pagination a MUST FIX — `.limit(500)` is a weaker substitute.
- **Migration 0032** — `idx_team_memberships_team_active` partial index, backs EP-08 N+1 fix.
- **Migration 0031** — extends `work_items_type_valid` CHECK with `story`/`milestone` using zero-downtime `ADD CONSTRAINT NOT VALID` + `VALIDATE CONSTRAINT` pattern (`backend/migrations/versions/0031_extend_work_item_types.py`). Downgrade refuses if offending rows exist. ORM `_WORK_ITEM_TYPES` in `orm.py:208` was out of sync with the domain enum; now fixed.
- **Dundun callback** verified to use shared session transaction + `SET LOCAL app.current_workspace` for RLS (`backend/app/presentation/controllers/dundun_callback_controller.py:81,146`) — prevents the callback from bypassing RLS when it commits across repos.
- **`JwtAdapter` singleton** — `@lru_cache(maxsize=1)` in `backend/app/presentation/dependencies.py:107` + injected via `Depends(get_jwt_adapter)` on the WS endpoint instead of per-connection instantiation.
- **Migration 0033** — workspace scoping (column + FK + btree index + RLS policy) on `conversation_threads`, `assistant_suggestions`, `gap_findings`. Backfill via work-item join; orphan threads dropped.

Gaps intentionally left un-ticked — **the entire middleware chain** in Group 1 (CorrelationID, RequestLogging), all CORS/CSP/CSRF enforcement, the Pydantic `extra="forbid"` sweep, full rate limiter middleware, cursor pagination, Redis cache-aside proper, N+1 detection middleware, SSE infrastructure. These are the bulk of EP-12 and none of them have started. When EP-12 enters formal delivery, the plan text is still accurate — most of it just hasn't been executed.

## EP-12 middleware wiring (2026-04-17) — phase 9 pass complete

Commits: 585072a (settings), 6a4d1c4 (wiring).

- `AppSettings` extended: `max_body_bytes: int = 1_048_576` (env `APP_MAX_BODY_BYTES`), `csp_overrides: dict[str,str] = {}` (env `APP_CSP_OVERRIDES` as `key=value,...`). 7 unit tests.
- `main.py`: old `CORSMiddleware` removed; `RequestLoggingMiddleware`, `BodySizeLimitMiddleware`, `CORSPolicyMiddleware`, `SecurityHeadersMiddleware` wired in LIFO order. 10 integration tests.
- Test delta: +17 tests (7 unit settings + 10 integration chain). Full unit suite: 1260 passed.

## EP-12 middleware scaffold (2026-04-17) — 6 modules shipped, un-wired

Shipped (modules + unit tests only — main.py untouched):

- **`RequestLoggingMiddleware`** (`app/presentation/middleware/request_logging.py`) — commit 82b1e6d. 7 tests.
- **`CORSPolicyMiddleware`** (`app/presentation/middleware/cors_policy.py`) — commit 1dcddcb. 9 tests.
- **`SecurityHeadersMiddleware`** (`app/presentation/middleware/security_headers.py`) — CSP + HSTS + X-Frame-Options. Commit 1e3d5c0. 8 tests.
- **`BodySizeLimitMiddleware`** (`app/presentation/middleware/body_size_limit.py`) — commit 74e291c. 7 tests.
- **`encode_cursor`/`decode_cursor`** (`app/presentation/pagination/cursor.py`) — HMAC-signed base64url. Commit 8640c3a. 9 tests.
- **Observability scaffolding** (`app/infrastructure/observability/metrics.py` + `tracing.py`) — no-op counter/histogram/span. Commit 0f223e8. 12 tests.

Total new unit tests: +52. Full suite: 1166 passed.

**Wiring order for main.py (phase 9 pass):**
```python
# Outermost → innermost (add_middleware is LIFO — last added runs first)
app.add_middleware(CorrelationIDMiddleware)                               # already exists
app.add_middleware(RequestLoggingMiddleware)                              # NEW — reads CorrelationID ContextVar
app.add_middleware(BodySizeLimitMiddleware,                               # NEW — early rejection before auth
                   max_body_bytes=settings.app.max_body_bytes,
                   large_body_prefixes=["/api/v1/attachments"],
                   large_body_limit=10 * 1024 * 1024)
app.add_middleware(CORSPolicyMiddleware,                                  # NEW — before auth so preflight works
                   allowed_origins=settings.app.cors_allowed_origins,
                   env=settings.app.env)
app.add_middleware(SecurityHeadersMiddleware,                             # NEW — wraps all responses
                   csp_overrides=getattr(settings.app, "csp_overrides", {}))
# RateLimitMiddleware — existing, already wired via slowapi
# AuthMiddleware — existing JWTAuthMiddleware
```
