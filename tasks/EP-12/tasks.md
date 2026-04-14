# EP-12 — Implementation Checklist

> **Propagation note (2026-04-14, decisions_pending.md #27)**: Observability is deferred. Sentry/Prometheus/OTel/Loki/product_events/LLM-metrics/health-dashboard items are obsolete. Re-plan at TDD time.

**Status: NOT STARTED**

TDD markers: [RED] = write failing test first | [GREEN] = implement to pass | [REFACTOR] = clean up

---

## Group 1 — Foundation (do this first, all other groups depend on it)

- [ ] [RED] Test: CorrelationIDMiddleware generates UUID when header absent, passes through when valid UUID present, rejects and regenerates invalid UUID
- [ ] [GREEN] Implement `CorrelationIDMiddleware` — inject/generate `X-Correlation-ID`, set on response header
- [ ] [RED] Test: structured log output includes `correlation_id`, `timestamp`, `level`, `logger`, `message` fields
- [ ] [GREEN] Configure structlog with JSON renderer and contextvars processor
- [ ] [GREEN] Wire CorrelationIDMiddleware to bind correlation_id into structlog contextvars per request
- [ ] [REFACTOR] Extract log configuration to `app/infrastructure/logging/setup.py`, import in `app/main.py`
- [ ] [RED] Test: `RequestLoggingMiddleware` logs method, path, status_code, duration_ms after each request
- [ ] [GREEN] Implement `RequestLoggingMiddleware`
- [ ] Document middleware chain order in `app/main.py` comments

---

## Group 2 — Security

### 2.1 Capability enforcement

- [ ] [RED] Test: `require_capabilities(["review"])` returns 403 when member lacks capability
- [ ] [RED] Test: returns 403 when workspace_id is invalid/missing
- [ ] [RED] Test: passes through when member has the required capability
- [ ] [RED] Test: superadmin bypass is explicit and logs the bypass
- [ ] [GREEN] Implement `require_capabilities` FastAPI dependency in `app/presentation/dependencies/auth.py`
- [ ] [REFACTOR] Ensure `require_capabilities` is added to all existing protected endpoints across other epics (scan and apply)

### 2.2 CORS

- [ ] [RED] Test: CORS middleware rejects origin not in ALLOWED_ORIGINS
- [ ] [RED] Test: app startup fails with ConfigurationError when ALLOWED_ORIGINS is empty in non-dev env
- [ ] [GREEN] Configure `CORSMiddleware` with ALLOWED_ORIGINS allowlist
- [ ] [GREEN] Add startup validation for ALLOWED_ORIGINS in settings

### 2.3 Rate limiting

- [ ] [RED] Test: unauthenticated endpoint returns 429 after 10 requests/min from same IP, with Retry-After header
- [ ] [RED] Test: authenticated endpoint returns 429 after 300 requests/min from same user
- [ ] [RED] Test: rate limit headers present on all responses (X-RateLimit-*)
- [ ] [GREEN] Implement `RateLimitMiddleware` with Redis sliding window counter
- [ ] [GREEN] Wire into middleware chain

### 2.4 Input validation

- [ ] [RED] Test: endpoint rejects unknown fields (extra="forbid")
- [ ] [RED] Test: file upload rejected if MIME type mismatch (magic bytes)
- [ ] [RED] Test: file upload rejected if size exceeds MAX_UPLOAD_BYTES
- [ ] [GREEN] Enforce `model_config = ConfigDict(extra="forbid")` on all Pydantic schemas (scan all existing schemas)
- [ ] [GREEN] Implement file validation utility in `app/application/validators/file_validator.py`

### 2.5 CSRF

- [ ] [RED] Test: state-changing endpoint returns 403 on missing/invalid CSRF token
- [ ] [GREEN] Implement CSRF token middleware for state-changing methods
- [ ] [GREEN] Frontend: auto-attach CSRF token header in API client

### 2.6 Content Security Policy

- [ ] [RED] Test: all HTML responses include CSP header with required directives
- [ ] [GREEN] Configure CSP header in Next.js `next.config.ts` headers section
- [ ] [GREEN] Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy` headers
- [ ] [GREEN] Implement `/api/v1/csp-report` endpoint (logs at WARN, no-op otherwise)

### 2.7 Audit log

- [ ] [RED] Test: login success writes audit record with required fields
- [ ] [RED] Test: 403 response writes audit record with outcome=failure
- [ ] [RED] Test: element status transition writes audit record
- [ ] [RED] Test: audit log write failure rolls back the originating operation
- [ ] [GREEN] Implement `AuditLogRepository.append()` (append-only, no update/delete methods)
- [ ] [GREEN] Integrate audit writes at: login, token refresh, 403 handler, status transitions, credential CRUD, export
- [ ] Verify audit log schema aligns with EP-10 design (no duplicate migration)

### 2.8 Secrets handling

- [ ] Audit all settings for hardcoded secrets (grep for common patterns: password, secret, key, token in source)
- [ ] [GREEN] Add startup validation: if any required secret is None in production, raise ConfigurationError with variable name
- [ ] [GREEN] Add `scrub_sensitive_data` before_send hook in Sentry init to strip Authorization headers

---

## Group 3 — Performance

### 3.1 Cursor-based pagination

- [ ] [RED] Test: list endpoint returns `pagination.cursor`, `has_next`, `total_count` in response
- [ ] [RED] Test: supplying cursor returns correct next page (keyset semantics)
- [ ] [RED] Test: page size defaults to 20, max 100, rejected above 100
- [ ] [GREEN] Implement `PaginationCursor` dataclass with encode/decode
- [ ] [GREEN] Implement `paginate()` utility for SQLAlchemy queries
- [ ] [GREEN] Apply to: inbox list, element list, member list, audit log list, search results
- [ ] [REFACTOR] Eliminate any offset-based pagination from existing endpoints

### 3.2 Redis caching

- [ ] [RED] Test: inbox list cache hit avoids DB query
- [ ] [RED] Test: inbox cache invalidated on element status change affecting assignee
- [ ] [RED] Test: Redis unavailable falls back to DB without raising 5xx
- [ ] [GREEN] Implement `CacheService` wrapping Redis in `app/infrastructure/cache/redis_cache.py`
- [ ] [GREEN] Apply caching per the cache key table in design.md

### 3.3 N+1 detection

- [ ] [GREEN] Implement `QueryCounterMiddleware` (SQLAlchemy event listener, contextvars counter)
- [ ] [GREEN] Wire WARNING log when query budget exceeded (dev + staging only, off in production)
- [ ] Run existing endpoints and fix any N+1 detected (likely in element list + member list)

### 3.4 DB indexes

- [ ] Audit existing migrations for missing composite indexes on `(workspace_id, created_at)`
- [ ] Audit FK columns for missing supporting indexes
- [ ] Add migration for any missing indexes found
- [ ] Add EXPLAIN ANALYZE output as comments to new migrations going forward (document in CLAUDE.md)

### 3.5 Long-operation SSE

- [ ] [RED] Test: `/api/v1/jobs/{job_id}/progress` streams SSE events with correct format
- [ ] [RED] Test: complete event sent when Celery task finishes
- [ ] [RED] Test: error event sent when Celery task fails
- [ ] [RED] Test: keepalive comment sent every 30s on idle connection
- [ ] [GREEN] Implement `JobProgressService` that reads job state from Redis
- [ ] [GREEN] Implement SSE endpoint `/api/v1/jobs/{job_id}/progress`
- [ ] [GREEN] Celery task base class that updates Redis job state on progress/complete/fail
- [ ] [GREEN] Frontend: hook `useJobProgress(jobId)` consuming the SSE stream

### 3.6 Frontend performance

- [ ] Audit all images: replace with `next/image` where missing
- [ ] Audit all list views: add virtual rendering (react-window) for lists >100 items
- [ ] Run Lighthouse CI in pipeline: fail on LCP >2.5s, CLS >0.1, TBT >300ms

---

## Group 4 — Observability

### 4.1 Correlation ID on frontend

- [ ] [RED] Test: API client generates UUID per request and sends X-Correlation-ID header
- [ ] [RED] Test: correlation_id shown in error UI when request fails
- [ ] [GREEN] Implement correlation ID generation in `lib/api-client.ts`
- [ ] [GREEN] Show correlation_id in ErrorBoundary fallback and toast error messages

### 4.2 Sentry backend

- [ ] [GREEN] Add sentry-sdk to dependencies (Python)
- [ ] [GREEN] Initialize Sentry in `app/main.py` with FastAPI, SQLAlchemy, Celery integrations
- [ ] [GREEN] Add `scrub_sensitive_data` before_send hook
- [ ] [RED] Test: unhandled exception is captured (mock Sentry client, verify capture_exception called)
- [ ] [RED] Test: handled integration failure calls capture_exception with correlation_id extra
- [ ] [GREEN] Inject correlation_id and user_id as Sentry tags in CorrelationIDMiddleware

### 4.3 Sentry frontend

- [ ] [GREEN] Add @sentry/nextjs to dependencies
- [ ] [GREEN] Configure sentry.client.config.ts and sentry.server.config.ts
- [ ] [GREEN] Wrap top-level layout in ErrorBoundary that captures to Sentry with correlation_id

### 4.4 Product event service

- [ ] [RED] Test: `ProductEventService.track()` calls backend with correct event schema
- [ ] [RED] Test: backend unavailability does not propagate exception (logs warning only)
- [ ] [GREEN] Implement `ProductEventService` and `ProductEventBackend` interface
- [ ] [GREEN] Implement Postgres-backed backend (append-only `product_events` table) ⚠️ originally MVP-scoped — see decisions_pending.md
- [ ] [GREEN] Emit events at: login, element created/submitted/reviewed/exported, search, integration sync/fail, member invite/remove

### 4.5 Integration failure visibility

- [ ] [RED] Test: Jira 401 marks integration as `credential_error`, emits integration.failed event, sends SSE notification to workspace admin
- [ ] [RED] Test: admin dashboard integration health section reflects failure streak
- [ ] [GREEN] Implement `integration_sync_log` table and repository
- [ ] [GREEN] Write integration failure banner query for dashboard

### 4.6 Monitoring dashboard (ops)

- [ ] [GREEN] Create DB view `v_endpoint_metrics` from request logs (requires structured request logging from Group 1)
- [ ] [GREEN] Create Celery queue depth endpoint: `/api/v1/ops/queue-depths` (ops-only capability)
- [ ] [GREEN] Create integration health endpoint: `/api/v1/ops/integration-health`
- [ ] [GREEN] Frontend ops dashboard page with the metrics from spec Scenario 6

---

## Group 5 — Responsive & Accessibility

### 5.1 Layout primitives

- [ ] [RED] Test (Storybook / component test): AppShell renders bottom nav on <640px, sidebar on >=1024px
- [ ] [RED] Test: BottomSheet traps focus, max-height 75vh, dismisses on submit
- [ ] [RED] Test: StickyActionBar stays visible when virtual keyboard appears
- [ ] [GREEN] Implement AppShell component
- [ ] [GREEN] Implement BottomSheet component
- [ ] [GREEN] Implement StickyActionBar component
- [ ] [GREEN] Implement DataTable with horizontal scroll container on mobile
- [ ] [GREEN] Implement EmptyState component (variant per context: inbox, search, filtered list, no-access)
- [ ] [GREEN] Implement SkeletonLoader variants matching inbox card, element detail, table row

### 5.2 Inbox mobile

- [ ] [RED] Test: inbox renders single-column cards on 375px viewport (no horizontal scroll)
- [ ] [RED] Test: inbox card tap target >=48dp
- [ ] [RED] Test: "Load more" present when items > 20
- [ ] [GREEN] Apply mobile-first layout to inbox page and card component

### 5.3 Element detail mobile

- [ ] [RED] Test: metadata accordion present on <640px
- [ ] [RED] Test: action bar is sticky at bottom on mobile
- [ ] [GREEN] Apply mobile-first layout to element detail page

### 5.4 Review actions mobile

- [ ] [RED] Test: review drawer uses BottomSheet on mobile, side drawer on desktop
- [ ] [RED] Test: submit button always visible in BottomSheet without internal scroll
- [ ] [GREEN] Wire review action component to BottomSheet on mobile

### 5.5 UI states

- [ ] [RED] Test: all data-dependent views show SkeletonLoader during fetch
- [ ] [RED] Test: EmptyState shown when API returns empty array
- [ ] [RED] Test: InlineError + Retry shown on 5xx/network timeout
- [ ] [RED] Test: form fields show inline error with aria-invalid on 422 response
- [ ] [GREEN] Apply to: inbox, element list, element detail, dashboard, member list, audit log

### 5.6 Accessibility

- [ ] [RED] Test: all interactive elements reachable by Tab in DOM order
- [ ] [RED] Test: modal dialogs trap focus
- [ ] [RED] Test: status badges have text label (not color alone)
- [ ] [RED] Test: `prefers-reduced-motion` disables skeleton shimmer
- [ ] [GREEN] Add aria-label to all icon buttons across all components
- [ ] [GREEN] Add aria-live region for dynamic content updates (notifications, status changes)
- [ ] Run axe-core in CI and fail on any accessibility violation with impact critical or serious

---

## DoD gate before any story is marked complete

Before any story in any epic is moved to "done":

- [ ] All items in the DoD checklist from `design.md` section 5 are checked
- [ ] `code-reviewer` agent run and findings addressed
- [ ] `review-before-push` run and clean

**Status: NOT STARTED**
