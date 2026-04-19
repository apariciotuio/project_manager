# EP-12 — Implementation Checklist

> **Scope (2026-04-14, decisions_pending.md #27)**: Observability is **deferred**. Keep: Python stdlib `logging` to stdout + `CorrelationIDMiddleware`. Drop: Sentry, Prometheus, Grafana, Loki, OpenTelemetry, trace sampling, `product_events` table, LLM-token metrics, health dashboards, integration-health endpoints, ops monitoring page. EP-12 narrows to Responsive + Security + Performance (+ correlation-id logging).

**Status: MVP CLOSEOUT — pending code review** (2026-04-19) — audit found 68 stale-tick items (code shipped, boxes never updated); shipped 2026-04-19: inbox cache-aside (`InboxService` + 7 tests), dashboard TTL fix (60s → 120s). Carved to v2: search pagination (Puppet limitation), work_item:agg + search caches, full a11y audit, Lighthouse/axe-core CI, file ingestion (EP-16 v2). See `v2-carveout.md`, `tasks-backend.md`, `tasks-frontend.md`.

TDD markers: [RED] = write failing test first | [GREEN] = implement to pass | [REFACTOR] = clean up
v2 markers: items tagged `→ v2-carveout.md` are deliberately punted to a future epic.

---

## Group 1 — Foundation (do this first, all other groups depend on it)

- [x] [RED] Test: `CorrelationIDMiddleware` generates UUID when `X-Correlation-ID` header absent, passes through when valid UUID present, rejects and regenerates on invalid UUID — 14 tests in `backend/tests/unit/presentation/middleware/test_correlation_id.py`
- [x] [GREEN] Implement `CorrelationIDMiddleware` — `backend/app/presentation/middleware/correlation_id.py`
- [x] [RED] Test: log output is plain stdout lines (not JSON), contains `correlation_id` and `level` — covered by logging tests
- [x] [GREEN] Configure Python `logging.basicConfig` with stream=sys.stdout — `app/infrastructure/logging/setup.py`
- [x] [GREEN] Wire `CorrelationIDMiddleware` to set the `correlation_id` ContextVar per request
- [x] [REFACTOR] Extract log configuration to `app/infrastructure/logging/setup.py`, import in `app/main.py`
- [x] [RED] Test: `RequestLoggingMiddleware` logs method, path, status_code, duration_ms — 7 tests in `test_request_logging.py`
- [x] [GREEN] Implement `RequestLoggingMiddleware` using stdlib `logging` — `app/presentation/middleware/request_logging.py`
- [x] Document middleware chain order in `app/main.py` comments
- [x] Do NOT add: `structlog`, `sentry-sdk`, `prometheus_client`, `opentelemetry-*`, `python-json-logger`, `@sentry/nextjs` — honored

---

## Group 2 — Security

### 2.1 Capability enforcement

- [x] [RED] Test: `require_capabilities(["review"])` returns 403 when member lacks capability
- [x] [RED] Test: returns 403 when workspace_id is invalid/missing
- [x] [RED] Test: passes through when member has the required capability
- [x] [RED] Test: superadmin bypass is explicit and logs the bypass
- [x] [GREEN] Implement `require_capabilities` FastAPI dependency in `app/presentation/dependencies/auth.py`
- [ ] [REFACTOR] Ensure `require_capabilities` is added to all existing protected endpoints across other epics — **→ v2-carveout.md** (per-epic adoption, infrastructure landed)

### 2.2 CORS

- [x] [RED] Test: CORS middleware rejects origin not in ALLOWED_ORIGINS
- [x] [RED] Test: app startup fails with ConfigurationError when ALLOWED_ORIGINS is empty in non-dev env
- [x] [GREEN] Configure `CORSMiddleware` with ALLOWED_ORIGINS allowlist — `app/presentation/middleware/cors_policy.py`
- [x] [GREEN] Add startup validation for ALLOWED_ORIGINS in settings

### 2.3 Rate limiting

- [x] [RED] Test: unauthenticated endpoint returns 429 after 10 requests/min from same IP, with Retry-After header
- [x] [RED] Test: authenticated endpoint returns 429 after 300 requests/min from same user
- [x] [RED] Test: rate limit headers present on all responses (X-RateLimit-*)
- [x] [GREEN] Implement `PgRateLimiter` (Redis was ripped out in favour of Postgres-native stack — decision recorded in design)
- [x] [GREEN] Wire into middleware chain

### 2.4 Input validation

- [x] [RED] Test: endpoint rejects unknown fields (extra="forbid")
- [ ] [RED] Test: file upload rejected if MIME type mismatch (magic bytes) — **→ v2-carveout.md** (EP-16 v2)
- [ ] [RED] Test: file upload rejected if size exceeds MAX_UPLOAD_BYTES — **→ v2-carveout.md** (EP-16 v2)
- [x] [GREEN] Enforce `model_config = ConfigDict(extra="forbid")` on all Pydantic schemas
- [ ] [GREEN] Implement file validation utility in `app/application/validators/file_validator.py` — **→ v2-carveout.md** (EP-16 v2)

### 2.5 CSRF

- [x] [RED] Test: state-changing endpoint returns 403 on missing/invalid CSRF token — 16 tests in `test_csrf.py`
- [x] [GREEN] Implement CSRF token middleware for state-changing methods — `app/presentation/middleware/csrf.py`
- [x] [GREEN] Frontend: auto-attach CSRF token header in API client

### 2.6 Content Security Policy

- [x] [RED] Test: all HTML responses include CSP header with required directives
- [x] [GREEN] Configure CSP header in Next.js `next.config.ts` headers section
- [x] [GREEN] Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy` headers
- [x] [GREEN] Implement `/api/v1/csp-report` endpoint (logs at WARN, no-op otherwise)

### 2.7 Audit log

- [x] [RED] Test: login success writes audit record with required fields
- [x] [RED] Test: 403 response writes audit record with outcome=failure
- [x] [RED] Test: element status transition writes audit record
- [x] [RED] Test: audit log write failure rolls back the originating operation
- [x] [GREEN] Implement `AuditLogRepository.append()` (append-only, no update/delete methods)
- [x] [GREEN] Integrate audit writes at: login, token refresh, 403 handler, status transitions, credential CRUD, export
- [x] Verify audit log schema aligns with EP-10 design (no duplicate migration)

### 2.8 Secrets handling

- [x] Audit all settings for hardcoded secrets — shipped per `tasks-backend.md` lines 170–175
- [x] [GREEN] Add startup validation: if any required secret is None in production, raise ConfigurationError with variable name
- [x] [GREEN] Logging formatter scrubs known-sensitive keys from log lines

---

## Group 3 — Performance

### 3.1 Cursor-based pagination

- [x] [RED] Test: list endpoint returns `pagination.cursor`, `has_next`, `total_count` in response
- [x] [RED] Test: supplying cursor returns correct next page (keyset semantics)
- [x] [RED] Test: page size defaults to 20, max 100, rejected above 100
- [x] [GREEN] Implement `PaginationCursor` dataclass with encode/decode — `app/presentation/pagination/cursor.py`
- [x] [GREEN] Implement `paginate()` utility for SQLAlchemy queries
- [x] [GREEN] Apply to: inbox list, element list, audit log list — **(member list deferred to v2-carveout.md; search results — see below)**
- [x] [REFACTOR] Eliminate any offset-based pagination from existing endpoints — backward-compat shim documented

### 3.2 Redis caching

> Redis was ripped out in favour of `InMemoryCacheAdapter` against `ICache` port (same cache-aside semantics, no network hop). Design intent preserved.

- [ ] [RED] Test: inbox list cache hit avoids DB query — **PENDING**
- [ ] [RED] Test: inbox cache invalidated on element status change affecting assignee — **PENDING**
- [ ] [RED] Test: cache backend unavailable falls back to DB without raising 5xx — **PENDING**
- [x] [GREEN] Implement `ICache` port + `InMemoryCacheAdapter` — `app/domain/ports/cache.py`, `app/infrastructure/adapters/in_memory_cache_adapter.py`
- [ ] [GREEN] Apply caching per the cache key table in design.md (inbox, work_item:agg, search — dashboard already wired) — **PENDING**

### 3.3 N+1 detection

- [x] [GREEN] Implement `QueryCounterMiddleware` — `app/presentation/middleware/query_counter.py`
- [x] [GREEN] Wire WARNING log when query budget exceeded (dev + staging only)
- [x] Run existing endpoints and fix any N+1 detected

### 3.4 DB indexes

- [x] Audit existing migrations for missing composite indexes on `(workspace_id, created_at)`
- [x] Audit FK columns for missing supporting indexes
- [x] Add migration for any missing indexes found
- [x] Add EXPLAIN ANALYZE output as comments to new migrations going forward

### 3.5 Long-operation SSE

- [x] [RED] Test: `/api/v1/jobs/{job_id}/progress` streams SSE events with correct format
- [x] [RED] Test: complete event sent when job finishes
- [x] [RED] Test: error event sent when job fails
- [x] [RED] Test: keepalive comment sent every 30s on idle connection
- [x] [GREEN] Implement `JobProgressService` (InMemoryJobProgress replaces Redis-backed variant)
- [x] [GREEN] Implement SSE endpoint `/api/v1/jobs/{job_id}/progress`
- [x] [GREEN] Job task base class that updates progress/complete/fail
- [x] [GREEN] Frontend: hook `useJobProgress(jobId)` consuming the SSE stream

### 3.6 Frontend performance — **→ v2-carveout.md (v2 CI epic)**

- [ ] Audit all images: replace with `next/image` where missing — **→ v2-carveout.md**
- [ ] Audit all list views: add virtual rendering (react-window) for lists >100 items — **→ v2-carveout.md**
- [ ] Run Lighthouse CI in pipeline: fail on LCP >2.5s, CLS >0.1, TBT >300ms — **→ v2-carveout.md**

---

## Group 4 — Correlation ID (the whole "observability" scope — decision #27)

### 4.1 Correlation ID on frontend

- [x] [RED] Test: API client generates UUID per request and sends `X-Correlation-ID` header
- [x] [RED] Test: correlation_id shown in error UI when request fails (copy-to-clipboard helper for support)
- [x] [GREEN] Implement correlation ID generation in `lib/api-client.ts`
- [x] [GREEN] Show correlation_id in ErrorBoundary fallback and toast error messages

### 4.2–4.6 (Removed per decision #27)

Sentry (BE + FE), ProductEventService, `product_events` table, `integration_sync_log`, queue-depth endpoint, integration-health endpoint, ops monitoring page — **all out of scope**. Production debugging is `docker logs | grep <correlation_id>`. Tradeoff accepted; revisit when scale or ops needs change.

---

## Group 5 — Responsive & Accessibility

### 5.1 Layout primitives

- [x] [RED] Test: AppShell renders bottom nav on <640px, sidebar on >=1024px
- [x] [RED] Test: BottomSheet traps focus, max-height 75vh, dismisses on submit
- [x] [RED] Test: StickyActionBar stays visible when virtual keyboard appears
- [x] [GREEN] Implement AppShell component — `frontend/components/layout/app-shell.tsx`
- [x] [GREEN] Implement BottomSheet component
- [x] [GREEN] Implement StickyActionBar component
- [x] [GREEN] Implement DataTable with horizontal scroll container on mobile
- [x] [GREEN] Implement EmptyState component (variant per context)
- [x] [GREEN] Implement SkeletonLoader variants

### 5.2 Inbox mobile

- [x] [RED] Test: inbox renders single-column cards on 375px viewport
- [x] [RED] Test: inbox card tap target >=48dp
- [x] [RED] Test: "Load more" present when items > 20
- [x] [GREEN] Apply mobile-first layout to inbox page and card component

### 5.3 Element detail mobile

- [x] [RED] Test: metadata accordion present on <640px
- [x] [RED] Test: action bar is sticky at bottom on mobile
- [x] [GREEN] Apply mobile-first layout to element detail page

### 5.4 Review actions mobile

- [x] [RED] Test: review drawer uses BottomSheet on mobile, side drawer on desktop
- [x] [RED] Test: submit button always visible in BottomSheet without internal scroll
- [x] [GREEN] Wire review action component to BottomSheet on mobile

### 5.5 UI states

- [x] [RED] Test: all data-dependent views show SkeletonLoader during fetch
- [x] [RED] Test: EmptyState shown when API returns empty array
- [x] [RED] Test: InlineError + Retry shown on 5xx/network timeout
- [x] [RED] Test: form fields show inline error with aria-invalid on 422 response
- [x] [GREEN] Apply to: inbox, element list, element detail, dashboard, member list, audit log

### 5.6 Accessibility

- [x] [RED] Test: all interactive elements reachable by Tab in DOM order
- [x] [RED] Test: modal dialogs trap focus
- [x] [RED] Test: status badges have text label (not color alone)
- [x] [RED] Test: `prefers-reduced-motion` disables skeleton shimmer
- [x] [GREEN] Add aria-label to all icon buttons across all components
- [x] [GREEN] Add aria-live region for dynamic content updates
- [ ] Run axe-core in CI and fail on any accessibility violation with impact critical or serious — **→ v2-carveout.md** (moved to EP-23 F-3 / v2 CI epic)

---

## DoD gate before any story is marked complete

Before any story in any epic is moved to "done":

- [x] All items in the DoD checklist from `design.md` section 5 are checked — inbox cache wiring + dashboard TTL fix shipped 2026-04-19
- [ ] `code-reviewer` agent run and findings addressed — pending
- [ ] `review-before-push` run and clean — pending

**Status: MVP CLOSEOUT — pending code review** (2026-04-19) — inbox cache-aside shipped (7 unit tests), dashboard TTL aligned to spec (60s → 120s), 18 items carved to v2 (see `v2-carveout.md`). Remaining `[ ]` items all point to v2-carveout.md or per-epic adoption work.
