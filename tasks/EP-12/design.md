# EP-12 Technical Design — Responsive, Security & Performance

> **Scope change (resolved 2026-04-14, decisions_pending.md #27)**: Observability is **deferred**. Prometheus, Grafana, Loki, OpenTelemetry, Sentry, trace sampling, LLM metrics, `product_events`, and health dashboards are out of scope. Only Python stdlib `logging` to stdout + `CorrelationIDMiddleware` remain. See `specs/observability/spec.md` for the reduced surface.

This document defines the canonical patterns for cross-cutting concerns. All other epics inherit these patterns. Deviating from them requires an explicit decision record.

---

## 1. Responsive — CSS Strategy

### Tailwind mobile-first breakpoints

```
default (no prefix) → <640px (mobile)
sm:                  → ≥640px (large phone landscape)
md:                  → ≥768px (tablet portrait)
lg:                  → ≥1024px (tablet landscape / small laptop)
xl:                  → ≥1280px (desktop)
```

Rule: write mobile styles first, use `md:` and `lg:` prefixes for wider layouts. Never write desktop styles and then "shrink" with `sm:max-*` breakpoints — that is the wrong direction.

### Layout primitives (shared components all epics use)

```
AppShell         — top bar + bottom nav (mobile) | sidebar + main (desktop)
PageContainer    — max-w-7xl, horizontal padding responsive
BottomSheet      — mobile action drawer, slides from bottom
StickyActionBar  — fixed bottom bar for primary actions on mobile
DataTable        — responsive: horizontal scroll container on mobile, full table on md+
EmptyState       — icon + heading + body + optional CTA
SkeletonLoader   — matches the layout of the target component
ErrorBoundary    — page-level + section-level variants
InlineError      — form field errors, section fetch errors
```

### Component mobile-first variants

Inbox card:
- Mobile: full-width stacked card, 48dp tap target, swipe-to-action
- Desktop: table row in DataTable

Element detail:
- Mobile: single column, metadata accordion, sticky action bar at bottom
- Desktop: two-column (metadata left, content right), inline action panel

Bottom sheet (review actions):
- Mobile only: slides from bottom, max-height 75vh, internal scroll
- Desktop: right-side drawer or inline panel

### Touch target enforcement

All interactive elements must have `min-h-[48px] min-w-[48px]`. Apply via Tailwind utility class `touch-target` defined in `tailwind.config.ts`:
```ts
// tailwind.config.ts
theme.extend.minHeight['touch'] = '48px'
theme.extend.minWidth['touch'] = '48px'
```

---

## 2. Security Middleware Stack

Order matters. Every request passes through this chain:

```
Request
  → CorrelationIDMiddleware        (inject/generate X-Correlation-ID)
  → RateLimitMiddleware            (Redis sliding window, per IP or per user)
  → CORSMiddleware                 (allowlist from ALLOWED_ORIGINS env var)
  → AuthMiddleware                 (validate JWT access token, attach user to request state)
  → CapabilityMiddleware           (per-endpoint, require_capabilities([...]))
  → InputValidationMiddleware      (Pydantic, handled by FastAPI)
  → Handler
```

Order matters: correlation-ID first so every downstream log line carries it; rate-limit before auth so anonymous floods are cheap to reject; CORS before auth so preflight doesn't bounce on missing JWT.

### `require_capabilities` decorator

```python
# app/presentation/dependencies/auth.py
def require_capabilities(capabilities: list[str]):
    async def dependency(
        workspace_id: UUID,
        current_user: AuthenticatedUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        member = await workspace_member_repo.get(db, workspace_id, current_user.id)
        if member is None:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
        missing = set(capabilities) - set(member.capabilities)
        if missing:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "missing": list(missing)})
    return Depends(dependency)
```

Usage in route:
```python
@router.post("/work-items/{work_item_id}/review")
async def review_work_item(
    work_item_id: UUID,
    body: ReviewRequest,
    _: None = require_capabilities(["review"]),
):
    ...
```

### CORS configuration

```python
# app/main.py
from starlette.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = settings.ALLOWED_ORIGINS  # list[str] from env, fails at startup if empty in prod

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-CSRF-Token"],
    max_age=600,
)
```

### Rate limiting (Redis sliding window)

```python
# app/infrastructure/rate_limiting/redis_rate_limiter.py
# Key: ratelimit:{identifier}:{window_start_minute}
# Uses Redis INCR + EXPIRE
# Returns (allowed: bool, remaining: int, reset_at: int)
```

Limits:
- Unauthenticated (login, OAuth, refresh): 10 req/min per IP
- Authenticated: 300 req/min per user_id

---

## 3. Performance Patterns

### Cursor-based pagination

```python
# Domain: PaginationCursor
@dataclass
class PaginationCursor:
    sort_value: Any        # value of the sort column at the boundary
    id: UUID               # tiebreaker

    def encode(self) -> str:
        return base64.b64encode(json.dumps([str(self.sort_value), str(self.id)]).encode()).decode()

    @classmethod
    def decode(cls, cursor: str) -> "PaginationCursor":
        data = json.loads(base64.b64decode(cursor))
        return cls(sort_value=data[0], id=UUID(data[1]))
```

Standard paginated response shape:
```json
{
  "data": [...],
  "pagination": {
    "cursor": "<base64>",
    "has_next": true,
    "total_count": 347
  }
}
```

All list endpoints use this shape. No offset pagination anywhere.

### Redis caching strategy

| Cache key pattern | TTL | Invalidation trigger |
|-------------------|-----|---------------------|
| `inbox:{user_id}:{workspace_id}[:type={item_type}]` | 30s | Element status change affecting assignee |
| `work_item:agg:{work_item_id}` | 60s | Comment added, attachment added |
| `dashboard:workspace:{workspace_id}` | 120s | Background refresh every 90s |
| `search:{workspace_id}:{hash(query)}` | 15s | Any element create/update in workspace |

Cache-aside pattern: read → miss → DB → write cache → return. Write-through for invalidation.

**Inbox filter-variant keys:** a filtered view (e.g. `?item_type=bug`) uses a distinct key `inbox:{user_id}:{workspace_id}:type=bug` so it does not poison the unfiltered entry. `InboxService.invalidate()` purges the base key only — filtered entries are bounded by the 30s TTL. This is an intentional trade-off: tracking every filter variant would require a scan API on `ICache` which today exposes only `get`/`set`/`delete`.

### N+1 detection in development

```python
# app/infrastructure/db/query_counter.py
# SQLAlchemy event listener: before_cursor_execute
# Increments per-request counter stored in contextvars
# After response: if count > budget[endpoint], emit WARNING log
```

### DB index requirements (mandatory per migration checklist)

Every migration touching a tenant-scoped table must:
1. Add composite index on `(workspace_id, created_at DESC)` if not present
2. Add index on any FK column not already indexed
3. Add GIN index on any `tsvector` column used for search
4. Include `EXPLAIN ANALYZE` output for the 3 most frequent queries as a migration comment

---

## 4. Observability Patterns

### Structured logging setup

```python
# app/infrastructure/logging/setup.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,   # inject correlation_id, user_id
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
```

Per-request context injection (in CorrelationIDMiddleware):
```python
structlog.contextvars.bind_contextvars(
    correlation_id=correlation_id,
    user_id=str(request.state.user_id) if hasattr(request.state, "user_id") else None,
    workspace_id=str(request.state.workspace_id) if hasattr(request.state, "workspace_id") else None,
)
```

### Correlation ID middleware

```python
# app/presentation/middleware/correlation_id.py
class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id or not is_valid_uuid(correlation_id):
            correlation_id = str(uuid4())
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

### Sentry / Prometheus / OpenTelemetry / PostHog — DEFERRED

Removed per resolution #27. No external error tracking, metrics, tracing, or product-analytics SDKs. Errors are logged to stdout via stdlib `logging`; operators tail logs by correlation ID. Re-introduction requires a new decision.

### Product event service — DEFERRED

No `product_events` table. No PostHog/Segment integration. The `ProductEventService` is not implemented. User-visible actions are captured in `audit_events` (EP-00/EP-10) when they affect security or admin surface; UX analytics are out of scope.

---

## 5. Definition of Done — Cross-epic checklist

Every story in every epic is "done" when ALL of the following are checked. Not a recommendation — a gate.

### Code

- [ ] All new code is fully typed (Python: no `Any` without comment; TS: `strict: true`, no `any`)
- [ ] No secrets hardcoded or logged
- [ ] Input validated at the boundary (Pydantic schema, FastAPI path types)

### Security

- [ ] Every new endpoint has `require_capabilities([...])` or an explicit `# No auth required: <reason>` comment
- [ ] New endpoints appear in the audit log for sensitive actions (per spec Scenario 9)
- [ ] OWASP checklist consulted for the change (parameterized queries, output escaping, no open redirect)

### Performance

- [ ] Query count verified: <=5 reads, <=3 writes for the endpoint
- [ ] Pagination applied to all list endpoints (cursor-based)
- [ ] Redis cache key documented if caching is used
- [ ] New indexes added to migration if any new filter column introduced

### Logging (observability deferred — resolution #27)

- [ ] All significant operations emit stdlib `logging` lines with correlation_id in context
- [ ] Errors are logged to stdout with full traceback; no Sentry
- [ ] No product-event instrumentation
- [ ] Integration failures are logged and recorded in `audit_events` (no `integration_sync_log` table)

### Responsive / Accessibility

- [ ] New pages/components render without horizontal scroll on 375px viewport
- [ ] All interactive elements meet 48dp touch target requirement
- [ ] Loading, empty, and error states implemented for every data-dependent view
- [ ] Keyboard navigation works; focus indicators visible
- [ ] `aria-label` on all icon buttons and non-descriptive interactive elements

### Tests

- [ ] RED phase committed before implementation
- [ ] All new endpoints have unit tests (service layer) and integration tests (HTTP layer)
- [ ] Edge cases covered: 403, 422, empty result, pagination boundary

### Review

- [ ] `code-reviewer` agent run
- [ ] `review-before-push` workflow run
- [ ] No `TODO` or `FIXME` left without a linked task

---

## Workspace Scoping Pattern (Mandatory)

CRIT-2 fix. Every resource in the system is owned by a workspace. The following rules are non-negotiable.

### Repository contract

All repository methods that fetch workspace-owned entities MUST accept `workspace_id` as a required parameter and include it in the WHERE clause. No UUID lookup may succeed across workspace boundaries.

```python
# domain/repositories/base.py
from abc import ABC, abstractmethod
from uuid import UUID
from typing import TypeVar, Generic

T = TypeVar("T")

class WorkspaceScopedRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: UUID, workspace_id: UUID) -> T | None:
        """Returns None (not 404) when id exists but belongs to a different workspace."""
        ...

    @abstractmethod
    async def list(self, workspace_id: UUID, **filters) -> list[T]:
        ...
```

Concrete example:
```python
# infrastructure/persistence/work_item_repository_impl.py
async def get(self, id: UUID, workspace_id: UUID) -> WorkItem | None:
    result = await self._session.execute(
        select(WorkItemORM).where(
            WorkItemORM.id == id,
            WorkItemORM.workspace_id == workspace_id,  # MANDATORY
        )
    )
    row = result.scalar_one_or_none()
    return WorkItemMapper.to_domain(row) if row else None
```

**Return 404 on workspace mismatch, never 403.** Returning 403 discloses existence of the resource.

### FastAPI dependency

`workspace_id` is extracted from the authenticated user's active membership — it is never taken from the request body or path.

```python
# app/presentation/dependencies/workspace.py
from fastapi import Depends, HTTPException
from uuid import UUID
from app.presentation.dependencies.auth import get_current_user

async def get_current_workspace_id(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UUID:
    """Single source of truth for workspace_id in request context."""
    if current_user.active_workspace_id is None:
        raise HTTPException(status_code=403, detail={"code": "NO_ACTIVE_WORKSPACE"})
    return current_user.active_workspace_id
```

Usage in every endpoint that touches a workspace-scoped resource:
```python
@router.get("/work-items/{work_item_id}")
async def get_work_item(
    work_item_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace_id),
    service: WorkItemService = Depends(get_work_item_service),
):
    return await service.get(work_item_id, workspace_id)
```

### Exceptions

The following tables are NOT workspace-scoped and must NOT use `WorkspaceScopedRepository`:
- `users` — global identity
- `workspaces` — owns the scoping
- `sessions` — scoped to user, not workspace (per db_review.md SD-8: canonical name is `sessions`, defined in EP-00)

All other tables with a `workspace_id` column must enforce scoping at the repository layer.

---

## CSRF Protection Design

CRIT-3 fix. Double-submit cookie pattern.

### Token lifecycle

1. On successful login or token refresh, the server generates a cryptographically random CSRF token (32 bytes, hex-encoded).
2. Server sets two cookies:
   - `session` (HttpOnly=true, Secure=true, SameSite=Strict) — the refresh token or session reference
   - `csrf_token` (HttpOnly=**false**, Secure=true, SameSite=Strict) — the CSRF token; JS must be able to read it
3. The client reads `csrf_token` cookie and sends it as `X-CSRF-Token` header on every state-changing request.

### CSRFMiddleware

```python
# app/presentation/middleware/csrf.py
EXEMPT_PATHS = {"/api/v1/auth/google", "/api/v1/auth/refresh"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("X-CSRF-Token")

        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "csrf_token_mismatch", "message": "CSRF validation failed"}},
            )
        return await call_next(request)
```

### Middleware chain position

`CSRFMiddleware` is inserted **after** `JWTAuthMiddleware` (requires authenticated user context) and before the handler:

```
CORSMiddleware
  → RateLimitMiddleware
  → JWTAuthMiddleware
  → CSRFMiddleware          ← inserted here
  → CapabilityCheckDecorator
  → InputValidationMiddleware
  → Handler
```

### Exempt endpoints

| Endpoint | Reason |
|----------|--------|
| `GET/HEAD/OPTIONS *` | Safe methods, no state change |
| `POST /api/v1/auth/google` | OAuth callback — no cookie yet |
| `POST /api/v1/auth/refresh` | Uses HttpOnly refresh token cookie; CSRF token not yet available |

---

## Shared SSE Infrastructure

EP-03 (conversation streaming) and EP-08 (real-time notifications) both require SSE. They must share a single implementation — two independent SSE stacks is not acceptable.

### Architecture

```
infrastructure/sse/
  redis_pubsub.py       # Redis pub/sub channel management (subscribe, publish, unsubscribe)
  sse_handler.py        # FastAPI StreamingResponse wrapper; reads from Redis channel, formats SSE frames
  channel_registry.py   # Maps channel names to their Redis key patterns
```

### Channel naming convention

| Consumer | Channel pattern | Published by |
|----------|----------------|--------------|
| EP-03 conversation | `sse:thread:{thread_id}` | `ClarificationService` after LLM token chunk |
| EP-08 notifications | `sse:user:{user_id}` | `NotificationService` on any notification event |

### SSE frame format (shared)

```
data: {"type": "<event_type>", "payload": {...}, "channel": "<channel>"}

event: done
data: {"message_id": "uuid"}
```

Both EP-03 and EP-08 SSE endpoints delegate to `SseHandler.stream(channel, request)`. The handler manages client disconnection cleanup (Redis unsubscribe on generator close).

### SSE Authentication (CRIT-1 fix)

Browser `EventSource` cannot set custom headers, so tokens must NOT be passed as query parameters. Query parameters appear in nginx/ALB access logs, browser history, and Referer headers.

**Stream-token pattern (mandatory)**:

1. Client calls `POST /api/v1/sse/stream-token` with a valid JWT in `Authorization: Bearer` header.
2. Server generates a short-lived (60s TTL), single-use opaque token, stores `{token: user_id + channel}` in Redis.
3. Client opens the SSE connection with `Authorization: Bearer <stream_token>` header.
4. `SseHandler` exchanges the stream token for user identity server-side, then deletes the token from Redis (single-use).
5. If the token is expired, not found, or already consumed → 401.

```python
# infrastructure/sse/stream_token_store.py
class StreamTokenStore:
    TTL_SECONDS = 60

    async def issue(self, user_id: UUID, channel: str) -> str:
        token = secrets.token_hex(32)
        await self._redis.set(
            f"sse_token:{token}",
            json.dumps({"user_id": str(user_id), "channel": channel}),
            ex=self.TTL_SECONDS,
        )
        return token

    async def consume(self, token: str) -> dict | None:
        """Returns payload and deletes token atomically. Returns None if missing/expired."""
        key = f"sse_token:{token}"
        payload = await self._redis.getdel(key)  # atomic get+delete
        return json.loads(payload) if payload else None
```

**If the browser EventSource API is used** (cannot set `Authorization` header): fall back to cookie-based auth with `SameSite=Strict`. The JWT session cookie is sent automatically. Do NOT use query params.

**Never log the `Authorization` header or stream token.** `RequestLoggingMiddleware` must strip the `Authorization` header from log output. SSE endpoint paths must not log query parameters.

### Redis pub/sub pattern

```python
# infrastructure/sse/redis_pubsub.py
class RedisPubSub:
    async def publish(self, channel: str, message: dict) -> None: ...
    async def subscribe(self, channel: str) -> AsyncIterator[dict]: ...
```

Single Redis connection pool shared across all SSE channels. Channel TTL (auto-expiry for abandoned channels): 5 minutes after last publish.

---

## 6. Dependency on other epics

| This design depends on | Reason |
|------------------------|--------|
| EP-00 (JWT + PKCE) | JWTAuthMiddleware validates access tokens from EP-00 |
| EP-10 (capabilities, Fernet, audit log) | `require_capabilities` reads `workspace_member.capabilities`; audit log schema from EP-10 |
| EP-03 (Celery queues) | Long-operation SSE uses EP-03 queue infrastructure |
| EP-08 (SSE) | Integration failure notifications use EP-08 SSE pattern |

EP-12 patterns must be available before any other epic's implementation begins. The middleware stack, logging setup, and DoD checklist are the first deliverables.
