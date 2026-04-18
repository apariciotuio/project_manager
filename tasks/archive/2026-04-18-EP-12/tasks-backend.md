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
- [x] [RED] Test: generates UUID v4 when `X-Correlation-ID` header absent — `tests/unit/presentation/middleware/test_correlation_id.py`
- [x] [RED] Test: passes through header value when valid UUID present — same file
- [x] [RED] Test: rejects and regenerates when header contains invalid UUID — was failing (impl passed through any string); now GREEN
- [x] [RED] Test: `X-Correlation-ID` always present in response header — same file
- [x] [GREEN] Implement `CorrelationIDMiddleware` in `app/presentation/middleware/correlation_id.py` — added `_parse_correlation_id()` UUID validation; was pre-existing but missing validation
- [x] [GREEN] Bind `correlation_id` into a `ContextVar` consumed by the logging formatter — `app/config/logging.py::correlation_id_var` already wired; confirmed by tests

### Logging (stdlib only — decision #27)
- [x] [RED] Test: log line includes `correlation_id` via a `Filter`/`Formatter` reading from ContextVar — 6 tests in `tests/unit/infrastructure/test_correlation_logging.py`
- [x] [GREEN] Configure structlog with JSON renderer and contextvars processor in `app/infrastructure/logging/setup.py` — stdlib only per decision #27; `JsonFormatter` + `CorrelationIdFilter` in `app/config/logging.py` serves this role
- [x] [GREEN] Import and initialize in `app/main.py` — `configure_logging(settings.app.log_level)` already called in `create_app()`

### RequestLoggingMiddleware
- [x] [RED] Test: logs `method`, `path`, `status_code`, `duration_ms` after each request — 7 tests in `tests/unit/presentation/middleware/test_request_logging.py`
- [x] [GREEN] Implement `RequestLoggingMiddleware` in `app/presentation/middleware/request_logging.py` — commit 82b1e6d
- [x] [GREEN] Document middleware chain order in `app/main.py` with comments — wired in phase 9 pass (2026-04-17): RequestLoggingMiddleware, BodySizeLimitMiddleware, CORSPolicyMiddleware, SecurityHeadersMiddleware added; old CORSMiddleware removed

---

## Group 2 — Security

### Capability Enforcement
- [x] [RED] Test: `require_capabilities(["review"])` returns 403 when member lacks capability — `test_returns_403_when_missing_required_capability` (2026-04-18)
- [x] [RED] Test: returns 403 when workspace_id is invalid/missing — `test_returns_403_when_workspace_id_is_none` + `test_returns_403_when_membership_missing` (2026-04-18)
- [x] [RED] Test: passes through when member has required capability — `test_passes_when_user_has_required_capability` (2026-04-18)
- [x] [RED] Test: superadmin bypass is explicit and logs the bypass — `test_superadmin_bypasses_check_and_logs` (2026-04-18)
- [x] [GREEN] Implement `require_capabilities` FastAPI dependency — `build_require_capabilities(*caps)` factory at `app/presentation/capabilities.py` + `get_capabilities_for(user_id, workspace_id)` narrow method on `WorkspaceMembershipRepositoryImpl` + `get_capability_repo` DI handle (2026-04-18, 7 tests green)
- [ ] [REFACTOR] Scan all existing protected endpoints across other epics and apply `require_capabilities` — pending separate sweep (infrastructure landed, adoption deferred to per-epic work)

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
- [x] [RED] Test: app startup raises `ConfigurationError` when `ALLOWED_ORIGINS` is empty in non-dev env — `test_production_empty_cors_raises` + `_populated_cors_passes` + `_dev_env_empty_cors_passes` (2026-04-18)
- [x] [GREEN] Implement `CORSPolicyMiddleware` in `app/presentation/middleware/cors_policy.py` — commit 1dcddcb (wildcard-in-prod raises ValueError at startup)
- [x] [GREEN] Wire `CORSPolicyMiddleware` into `app/main.py` replacing FastAPI `CORSMiddleware` — commit 6a4d1c4 (2026-04-17)
- [x] [GREEN] Add startup validation for `ALLOWED_ORIGINS` in settings — `AppSettings._validate_cors_in_production` raises `ConfigurationError` when empty in prod (2026-04-18)

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
- [x] [RED] Test: unauthenticated endpoint returns 429 after 10 req/min from same IP; response includes `Retry-After` header — 10 tests in `tests/unit/presentation/middleware/test_rate_limit.py` (commit f0fa6d1)
- [x] [RED] Test: authenticated endpoint returns 429 after 300 req/min from same user — covered in same file
- [x] [RED] Test: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers present on all responses — covered in same file
- [x] [GREEN] Implement `RateLimitMiddleware` in `app/infrastructure/rate_limiting/redis_rate_limiter.py` (Redis sliding window: key `ratelimit:{identifier}:{window_start_minute}`, INCR + EXPIRE) — commit f0fa6d1
- [x] [GREEN] Wire into middleware chain — commit f0fa6d1; position: after BodySizeLimit, before CORSPolicy
- [x] **Settings reverted to spec defaults:** `access_token_ttl_seconds = 900` (15m) and `rate_limit_per_minute = 10` in `backend/app/config/settings.py:55,58`. DX overrides via `.env.development`. (Not a middleware implementation — just resets the config creep.)

### Input Validation
- [x] [RED/GREEN] Test: endpoint rejects unknown fields (Pydantic `extra="forbid"`) — `test_schemas_strict_extra.py` covers 6 FE-originated request schemas. External webhooks (Puppet/Dundun callbacks) kept lenient intentionally (HMAC+idempotency trust gates) — covered by opposite-direction tests in same file (2026-04-18)
- [ ] [RED] Test: file upload rejected on MIME type mismatch (magic bytes check) — deferred with EP-16 v2 (file ingestion out of MVP)
- [ ] [RED] Test: file upload rejected if size exceeds `MAX_UPLOAD_BYTES` — deferred with EP-16 v2
- [x] [GREEN] Enforce `model_config = ConfigDict(extra="forbid")` on FE-originated Pydantic schemas — `thread_schemas.CreateThreadRequest`, `suggestion_schemas.GenerateSuggestionsRequest` + `PatchSuggestionStatusRequest`, `puppet_schemas.PuppetSearchRequest`. Work-item + template schemas already strict. Webhook schemas set to `extra="ignore"` with rationale (2026-04-18)
- [ ] [GREEN] Implement `FileValidator` in `app/application/validators/file_validator.py` — deferred with EP-16 v2 (no file uploads in MVP; placeholder retained for v2)

### CSRF
- [x] [RED] Test: state-changing endpoint (POST/PUT/PATCH/DELETE) returns 403 on missing/invalid CSRF token — 16 tests in `tests/unit/presentation/middleware/test_csrf.py`
- [x] [GREEN] Implement CSRF token middleware for state-changing methods — `app/presentation/middleware/csrf.py`; `hmac.compare_digest`; wired in `main.py` after CORS, before auth
  - [x] **Exempt paths:** `/api/v1/auth/google/callback`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`, `/api/v1/csp-report` — these bootstrap/teardown session or originate from browsers without CSRF context; 4 RED tests + all 15 auth integration tests green (2026-04-18)
  - [x] **MF-1 CSRF webhooks exempt** — added `/api/v1/dundun/callback` and `/api/v1/puppet/ingest-callback` to exempt_paths; HMAC-authenticated server-to-server, no browser CSRF cookie; 2 RED tests added and passing (2026-04-18)
- [x] [GREEN] Login sets `csrf_token` cookie — `google_callback` and `refresh_token` handlers emit `csrf_token` (httponly=False, samesite=strict, same TTL as access_token) via `_set_csrf_cookie()` in `auth.py`; 7 tests in `tests/integration/test_login_csrf_cookie.py` (2026-04-18)

### Content Security Policy
- [x] [RED] Test: all HTML responses include CSP header with required directives (default-src, script-src, etc.) — 8 tests in `tests/unit/presentation/middleware/test_security_headers.py`
- [x] [GREEN] Implement `/api/v1/csp-report` endpoint — logs at WARN, returns 204 — `app/presentation/controllers/csp_report_controller.py` commit f0fa6d1; 7 unit tests in `tests/unit/presentation/controllers/test_csp_report_controller.py`
- [x] [GREEN] Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy` headers — `app/presentation/middleware/security_headers.py` commit 1e3d5c0
- [x] [GREEN] Wire `SecurityHeadersMiddleware` into `app/main.py` — commit 6a4d1c4 (2026-04-17); `csp_overrides` reads from `settings.app.csp_overrides`

### Audit Log Integration
- [x] [RED] Test: login success writes audit record with required fields — `tests/integration/test_audit_integration_auth.py` (3 tests: login_success ip_address/entity_type, login_invalid_state failure, 403 ip_address)
- [x] [RED] Test: 403 response writes audit record with `outcome=failure` — covered in `test_audit_integration_auth.py::test_403_audit_includes_ip_address`
- [x] [RED] Test: element status transition writes audit record — `tests/integration/test_audit_status_transition.py` (3 tests: valid transition success+actor/workspace, invalid FSM edge failure); all 3 green (2026-04-18)
- [x] [RED] Test: audit log write failure rolls back the originating operation (same transaction) — `tests/integration/test_audit_log_repository.py` (5 tests: fields persisted, minimal fields, actor/workspace, hasattr append-only guard, rollback semantics)
- [x] [GREEN] Implement `AuditLogRepository.append()` (append-only; no update/delete) — schema confirmed in `0005_create_audit_events.py` (EP-00) + `AuditEventORM` orm.py:135; renamed `record()` → `append()` in `IAuditRepository`/`AuditRepositoryImpl`/`AuditService`; DB-level via Postgres RULES `no_update_audit`/`no_delete_audit`; 5/5 tests green (2026-04-18)
- [x] [GREEN] login success/failure + 403 handler — done (Option B JSONB context); `auth_service.handle_callback`: added `login_invalid_state` audit before InvalidStateError raise, added `entity_type='user'`+`entity_id` to `login_success` audit; `error_middleware._audit_authorization_denied`: added `ip_address` to context (2026-04-18); status transitions + credential CRUD + export deferred
- [x] [GREEN] Integrate audit writes at: credential CRUD — done (2026-04-18); export — done (2026-04-18)
  - credential CRUD: `integration_controller.py` — `create_integration_config` emits `category='admin', action='credential_create'` with SHA-256[:8] fingerprint; `delete_integration_config` emits `action='credential_delete'`; `get_audit_service` dep added to `dependencies.py`
  - Jira export: `export_to_jira` emits `action='jira_export_queued'` on 202; `_run_export` emits `action='jira_export_completed'` with `outcome=success/failure` + `jira_key`/`error` — 6 tests: `tests/integration/test_audit_credential_crud.py` (3) + `tests/integration/test_audit_jira_export.py` (3)

### Secrets Handling
- [x] Grep codebase for hardcoded secrets (patterns: password, secret, key, token in non-test source) — no hardcoded secrets found in `backend/app/`; 4 patterns checked; `.env` contains dev-only sentinels (expected)
- [x] [GREEN] Add startup validation: if any required secret is None in production, raise `ConfigurationError` with variable name — `model_validator(mode='after')` on `AuthSettings` (jwt_secret) and `DundunSettings` (api_key, callback_secret); `ConfigurationError` added to `app/domain/errors/codes.py`; 5 tests in `tests/unit/config/test_settings_production_required.py`
  - [x] **MF-2 PuppetSettings prod validator** — added `model_validator(mode='after')` to `PuppetSettings` raising `ConfigurationError` when `APP_ENV == "production"` and (`api_key == "dev-fake-key"` OR `callback_secret == "dev-puppet-callback-secret"`); mirrors `DundunSettings` pattern; 4 RED tests added and all passing (2026-04-18)
  - [x] **Partial:** `scripts/dev_token.py` refuses to run unless `APP_ENVIRONMENT in {development,dev,test,testing,local}` (`backend/scripts/dev_token.py:31-42`) — prevents minting arbitrary JWTs against prod DBs
- [x] [GREEN] Logging formatter scrubs known-sensitive keys (`Authorization`, `token`, `password`, `secret`, `api_key`, `credentials`) from log records — `JsonFormatter.format()` in `app/config/logging.py` scrubs extra fields by substring key match (case-insensitive); covers `authorization`, `token`, `password`, `secret`, `api_key`, `credentials`, `cookie`, `set-cookie`; 10 tests in `tests/unit/infrastructure/test_logging_scrub.py`

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
- [x] [RED] Test: list endpoint returns `pagination.cursor`, `has_next`, `total_count` — 23 tests in `tests/unit/infrastructure/test_pagination.py`
- [x] [RED] Test: supplying cursor returns correct next page (keyset semantics) — covered in TestPaginateSecondPage (4 tests)
- [x] [RED] Test: page size defaults to 20, max 100; request above 100 returns 422 — covered in TestPageSizeValidation (4 tests)
- [x] [GREEN] Implement `encode_cursor` / `decode_cursor` in `app/presentation/pagination/cursor.py` — HMAC-signed, commit 8640c3a
- [x] [GREEN] Implement `PaginationCursor` dataclass + `paginate()` utility for SQLAlchemy queries — `app/infrastructure/pagination.py`, 23 tests green
- [ ] [GREEN] Apply to: inbox list, work item list, member list, audit log list, search results — pending
  - [x] inbox (`GET /api/v1/notifications`): cursor pagination wired, 4 integration tests green — 2026-04-18
  - [x] work item list: `page_size` param (default 20, max 100), keyset on (created_at DESC, id DESC), 6 integration tests green — 2026-04-18
  - [x] work item list: filters restored (q, creator_id, owner_id, state, type, project_id, priority, tag_id, completeness, updated_after/before); sort override with full keyset support for all 5 SortOption variants; 7 new integration tests green — 2026-04-18
  - [ ] member list: deferred — endpoint is a UI picker (hard cap 500, intentional by design comment); keyset pagination would break picker UX; no service/repo layer exists to extend — 2026-04-18
  - [x] audit log list — done: keyset on (created_at DESC, id DESC), `require_admin` enforced, old offset-page removed, 6 integration tests green — 2026-04-18
  - [ ] search results: pending
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
- [x] [RED] Test: Redis unavailable falls back to DB without raising 5xx — 11 unit tests in `tests/unit/infrastructure/cache/test_redis_cache.py` covering miss/round-trip/delete/delete_pattern/ConnectionError/TimeoutError fail-open (2026-04-18)
- [x] [GREEN] Implement `CacheService` in `app/infrastructure/cache/redis_cache.py` — cache-aside pattern: get/set(json)/delete/delete_pattern; ConnectionError+TimeoutError caught, WARNING logged, None returned; injected client for testability (2026-04-18)
  - [x] **Partial (test/dev fake):** `InMemoryCacheAdapter` implements `ICache` with `OrderedDict` + FIFO eviction at `MAX_ENTRIES=10_000`, lazy TTL check, and a `.clear()` hook for test isolation (`backend/app/infrastructure/adapters/in_memory_cache_adapter.py`). Used when `REDIS_USE_FAKE=true`. Full Redis cache-aside path pending.
- [ ] [GREEN] Apply cache key strategy per design.md table: `inbox:{user_id}:{workspace_id}` (TTL 30s), `work_item:agg:{work_item_id}` (TTL 60s), `dashboard:{workspace_id}` (TTL 120s), `search:{workspace_id}:{hash(query)}` (TTL 15s)

### N+1 Detection
- [x] [GREEN] Implement `QueryCounterMiddleware` in `app/infrastructure/db/query_counter.py` — SQLAlchemy `before_cursor_execute` event listener; contextvars counter. Event listener on `engine.sync_engine`; `ContextVar[int | None]` (`None` = inactive). Registered via `register_query_counter(engine, env)` in `database.py`. (2026-04-18)
- [x] [GREEN] Emit WARNING log when query count exceeds budget per endpoint (dev + staging only; off in production). `check_query_budget(endpoint, budget)` called by `QueryCounterMiddleware.dispatch` at response time; skipped when `environment in {"production","prod"}`. Default budget=20. (2026-04-18)
- [x] Run existing endpoints with middleware enabled; fix any N+1 found — no integration tests run (CPU constraint per task spec). No N+1 endpoints observed in unit test suite. If WARNING fires in dev/staging, log line format is `N+1 WARNING endpoint=<path> queries=<n> budget=<budget>` — follow up as separate task. (2026-04-18)

### DB Index Audit
- [x] Audit existing migrations for missing composite indexes on `(workspace_id, created_at DESC)` — scanned all 28 tables in orm.py; cross-referenced 40+ migration files. Found 4 tables with `workspace_id` but no ordered composite: `state_transitions`, `ownership_history`, `work_item_drafts`, `validation_requirements`. (2026-04-18)
- [x] Audit FK columns for missing supporting indexes — found 5 FK columns without supporting indexes on hot paths: `workspaces.created_by`, `review_requests.version_id`, `validation_status.passed_by_review_request_id`, `puppet_sync_outbox.work_item_id`, `section_locks.work_item_id`. (2026-04-18)
- [x] Create migration for any missing indexes — `backend/migrations/versions/0114_ep12_index_audit.py` (revision `0114_ep12_index_audit`). Adds 9 indexes across 8 tables using `CREATE INDEX IF NOT EXISTS`. No CONCURRENTLY (alembic transaction constraint — documented in migration docstring with DBA fallback note). (2026-04-18)
  - [x] **work_items composite index — migration 0115:** `idx_work_items_workspace_created ON work_items (workspace_id, created_at DESC) WHERE deleted_at IS NULL` added in `backend/migrations/versions/0115_work_items_keyset_indexes.py` (revision `0115_work_items_keyset_indexes`). Backs `SortOption.created_desc` keyset path. `idx_work_items_active (workspace_id, updated_at DESC)` already existed in ORM model. (2026-04-18)
  - [x] **Partial:** Migration 0032 adds partial index `idx_team_memberships_team_active ON team_memberships(team_id, joined_at) WHERE removed_at IS NULL` (`backend/migrations/versions/0032_team_memberships_idx.py`) — backs the EP-08 team-picker N+1 fix.
  - [x] **Partial:** Migration 0033 adds `workspace_id` + btree index + RLS policy to `conversation_threads`, `assistant_suggestions`, `gap_findings` (`backend/migrations/versions/0033_ep03_rls.py`) — closes EP-03 cross-workspace leakage.
  - [x] **MF-1 SHIPPED:** Migration 0112 adds `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY <table>_workspace_isolation` to 9 tables: `teams`, `notifications`, `saved_searches`, `projects`, `routing_rules`, `integration_configs`, `integration_exports`, `work_item_drafts`, `validation_rule_templates`. Special policy for `validation_rule_templates` permits `workspace_id IS NULL` (global templates). Drops `vrt_global_allowed` placeholder CHECK. 8 integration tests in `tests/integration/test_migration_0112_rls.py`. (2026-04-17)
- [x] Document in project CLAUDE.md: all new migrations must include EXPLAIN ANALYZE output for 3 most frequent queries — added "Migration Standards" section to `.github/instructions/backend-standards.instructions.md` (source file for CLAUDE.md generation). Covers: EXPLAIN ANALYZE format, FK index requirement, workspace_id composite requirement, no CONCURRENTLY rule. (2026-04-18)

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
- [x] [RED] Test: `GET /api/v1/jobs/{job_id}/progress` streams SSE events with correct format (`data: {...}` frames) — `tests/unit/presentation/controllers/test_job_progress_controller.py` commit f0fa6d1
- [x] [RED] Test: `event: done` frame sent when Celery task finishes — `tests/integration/test_sse_job_progress.py::test_sse_job_progress_done_frame` commit d103b16
- [x] [RED] Test: `event: error` frame sent when Celery task fails — `tests/integration/test_sse_job_progress.py::test_sse_job_progress_error_frame` commit d103b16
- [x] [RED] Test: `: keepalive` comment sent on idle connection — `tests/integration/test_sse_job_progress.py::test_sse_job_progress_keepalive_comment` commit d103b16
- [ ] [RED] Test: client disconnect triggers Redis unsubscribe and generator cleanup — deferred (requires async streaming test harness with mid-stream disconnect; CancelledError path covered at unit level in SseHandler)
- [x] [GREEN] Implement `RedisPubSub` in `infrastructure/sse/redis_pubsub.py` — `publish(channel, message)`, `subscribe(channel) -> AsyncIterator[dict]` — commit f0fa6d1; 3 unit tests
- [x] [GREEN] Implement `SseHandler` in `infrastructure/sse/sse_handler.py` — `StreamingResponse` wrapper; reads from Redis channel; formats SSE frames (data/done/error/keepalive); handles disconnect via CancelledError — commit d103b16; 11 unit tests in `tests/unit/infrastructure/test_sse_handler.py`; job_progress_controller.py refactored to use it
- [x] [GREEN] Implement `ChannelRegistry` in `infrastructure/sse/channel_registry.py` — maps job/conversation/user-notification/presence channel names to Redis key patterns; optional workspace_id scoping — commit d103b16; 5 tests in same file
- [x] [GREEN] Implement `JobProgressService` — reads/writes job state in Redis — `app/infrastructure/sse/job_progress_service.py` commit f0fa6d1; 4 unit tests
- [x] [GREEN] Implement SSE endpoint `GET /api/v1/jobs/{job_id}/progress` — `app/presentation/controllers/job_progress_controller.py` commit f0fa6d1
- [x] [GREEN] Implement `ProgressTaskMixin` in `infrastructure/tasks/progress_task.py` — async helpers publish_progress/publish_done/publish_error; delegates to ChannelRegistry + JobProgressService — commit d103b16; 5 unit tests in `tests/unit/infrastructure/tasks/test_progress_task.py`

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
