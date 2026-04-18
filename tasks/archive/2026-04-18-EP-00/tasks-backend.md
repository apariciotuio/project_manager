# EP-00 Backend Tasks — Access, Identity & Bootstrap

Branch: `feature/ep-00-backend`
Refs: EP-00

---

## API Contract (Frontend Dependency)

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|---------|
| GET | `/api/v1/auth/google` | No | — | 302 → Google OAuth URL |
| GET | `/api/v1/auth/google/callback` | No | `?code=X&state=Y` | 302 → `/workspace/{slug}` + Set-Cookie |
| POST | `/api/v1/auth/refresh` | Refresh cookie | — | 200 + Set-Cookie (new access_token) |
| POST | `/api/v1/auth/logout` | Access cookie | — | 204 + clear cookies |
| GET | `/api/v1/auth/me` | Access cookie | — | `{ data: { id, email, full_name, avatar_url, workspace_id, workspace_slug, is_superadmin: boolean } }` |

Error envelope: `{ error: { code: string, message: string, details: {} } }`

---

## Phase 0 — Project Setup

- [x] `backend/` structure exists: `app/presentation/{controllers,middleware}/`, `app/application/services/`, `app/domain/{models,repositories}/`, `app/infrastructure/{persistence,adapters,jobs}/` — 2026-04-15
- [x] Dependencies in `pyproject.toml`: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `psycopg[binary]`, `alembic`, `pydantic-settings`, `celery[sqlalchemy]`, `httpx`, `python-jose[cryptography]`, `python-multipart`, `slowapi`, `orjson`. No `redis[asyncio]`. — 2026-04-15
- [x] `AuthSettings` carries `google_client_id`/`_secret`/`redirect_uri`, `jwt_secret`/`_algorithm`/`_expire_minutes`, `access_token_ttl_seconds=900`, `refresh_token_ttl_seconds=2592000`, `oauth_state_ttl_seconds=300`, `rate_limit_per_minute=10`, `allowed_domains`, `seed_superadmin_emails`. — 2026-04-15
- [x] Alembic configured for async SQLAlchemy in `migrations/env.py`; 6 revisions apply cleanly against testcontainer. — 2026-04-15
- [x] pytest-asyncio auto mode in `pyproject.toml`; session-scoped Postgres testcontainer in `tests/conftest.py`. — 2026-04-15

**Status: COMPLETED** (2026-04-15)

### Acceptance Criteria — Phase 0

WHEN `alembic upgrade head` is run against an empty DB
THEN all migrations apply without error and `alembic_version` reflects the latest revision

WHEN `pytest` is run with no backend code implemented
THEN the test runner starts without import errors; test DB fixture creates and tears down schema correctly

WHEN required env vars are missing
THEN app startup raises `pydantic_settings.ValidationError` (not a silent None default)

---

## Phase 1 — Domain Models

> Follow RED → GREEN → REFACTOR. No implementation code before a failing test.

### User Entity

- [x] [RED] Write unit tests for `User` entity: `from_google_claims()` factory sets all fields, `update_from_google()` merges name/avatar, email validation rejects invalid formats — 2026-04-15, 19 tests in `tests/unit/domain/test_user.py`
- [x] [GREEN] Implement `domain/models/user.py` — `User` dataclass (no ORM decorators), fields: `id`, `google_sub`, `email`, `full_name`, `avatar_url`, `status`, `is_superadmin`, `created_at`, `updated_at` — 2026-04-15
- [x] [REFACTOR] Verify `User` has zero imports from infrastructure or application layers — confirmed; only stdlib + uuid — 2026-04-15

### Session Entity

- [x] [RED] Write unit tests for `Session` entity: `is_expired()` boundary at `now()`, `is_revoked()` when `revoked_at` is set, `token_hash` is SHA-256 of opaque token, `revoke()` is idempotent — 2026-04-15, 11 tests in `tests/unit/domain/test_session.py`
- [x] [GREEN] Implement `domain/models/session.py` — `Session` entity with `hash_token` static, `create` factory, lifecycle helpers — 2026-04-15

### Workspace Entity

- [x] [RED] Write unit tests for `Workspace` entity: slug generation from email domain, `derive_name_from_domain()` strips `@` and TLD (handles compound SLDs like `.co.uk`), public provider detection (gmail, yahoo, 15 providers) returns generic slug with random suffix — 2026-04-15, 25 tests in `tests/unit/domain/test_workspace.py`
- [x] [GREEN] Implement `domain/models/workspace.py` — `Workspace` entity with `derive_name_from_domain`, `generate_slug`, `create_from_email` — 2026-04-15
- [x] [GREEN] Implement `domain/models/workspace_membership.py` — `WorkspaceMembership` entity with `state` FSM (`invited`/`active`/`suspended`/`deleted`), 15 tests in `tests/unit/domain/test_workspace_membership.py` — 2026-04-15

- [x] [REFACTOR] Review all domain models: no ORM imports, no HTTP concerns, pure dataclasses — 2026-04-15, confirmed via ruff + mypy clean on `app/domain/models/`

### Acceptance Criteria — Phase 1

See also: specs/auth/spec.md, specs/bootstrap/spec.md

WHEN `User.from_google_claims()` is called with `sub`, `email`, `name`, `picture`
THEN all fields are set; `id` is a new UUID; `status = active`

WHEN `User.from_google_claims()` receives a `null` or empty `email`
THEN it raises `ValueError` with message identifying the missing field

WHEN `User.update_from_google()` is called on an existing user with different `name` and `picture`
THEN `full_name` and `avatar_url` are updated; `id`, `google_sub`, `created_at` are unchanged

WHEN `Session.is_expired()` is called and `expires_at` equals `now()`
THEN it returns True (boundary — expired at exactly TTL)

WHEN `Workspace.derive_name_from_domain()` receives `"john@acme.io"`
THEN it returns `"Acme"` (domain part, TLD stripped, title-cased)

WHEN `Workspace.derive_name_from_domain()` receives `"john@gmail.com"`
THEN it returns `"My Workspace"` (public provider fallback)
AND the slug is generated as `my-workspace-<6 random chars>`

---

## Phase 2 — Repository Interfaces

- [x] Implement `domain/repositories/user_repository.py` — `IUserRepository` ABC: `get_by_id`, `get_by_google_sub`, `get_by_email`, `upsert` — 2026-04-15
- [x] Implement `domain/repositories/session_repository.py` — `ISessionRepository` ABC: `create`, `get_by_token_hash`, `revoke`, `delete_expired` — 2026-04-15
- [x] Implement `domain/repositories/workspace_repository.py` — `IWorkspaceRepository` ABC: `create`, `get_by_id`, `get_by_slug`, `slug_exists` — 2026-04-15
- [x] Implement `domain/repositories/workspace_membership_repository.py` — `IWorkspaceMembershipRepository` ABC: `create`, `get_by_user_id`, `get_active_by_user_id`, `get_default_for_user` — 2026-04-15
- [x] Implement `domain/repositories/oauth_state_repository.py` — `IOAuthStateRepository` ABC: `create`, `consume` (DELETE RETURNING), `cleanup_expired` — 2026-04-15
- [x] Smoke tests that ABCs reject direct instantiation — 5 parametrized cases in `tests/unit/domain/test_repository_interfaces.py` — 2026-04-15

### Acceptance Criteria — Phase 2

WHEN any repository method is called on a concrete implementation that is not yet injected
THEN Python raises `TypeError` at construction time (interfaces are uninstantiable ABCs)

WHEN `IUserRepository.upsert()` is called with the same `google_sub` twice
THEN the second call updates the existing record (no duplicate row)
AND the returned `User` has the same `id` as the first call

---

## Phase 3 — Database Migrations

- [x] Alembic migration `0001_create_users`: `users` + CHECK status + pgcrypto extension — 2026-04-15
- [x] Alembic migration `0002_create_sessions`: FK to users (CASCADE), `token_hash` unique, indexes on `user_id` and `expires_at` — 2026-04-15
- [x] Alembic migration `0003_create_workspaces`: FK `created_by` → users, unique `slug`, CHECK status — 2026-04-15
- [x] Alembic migration `0004_create_workspace_memberships`: CHECK state in 4 values, UNIQUE `(workspace_id, user_id)`, indexes `user_id` + `(workspace_id, state)` — 2026-04-15
- [x] Alembic migration `0005_create_audit_events`: unified table with JSONB `before_value/after_value/context`, 4 composite indexes with `created_at DESC`, `RULE no_update_audit` + `RULE no_delete_audit` for append-only — 2026-04-15
- [x] Alembic migration `0006_create_oauth_states`: `state PK`, `verifier`, `expires_at`, index on `expires_at` — 2026-04-15
- [x] Verify all migrations apply and roll back cleanly against local dev DB — confirmed `alembic upgrade head` + `downgrade base` + re-upgrade roundtrip — 2026-04-15
- [x] Integration tests against testcontainer: every expected table lands, CHECK constraints reject invalid status/state, `audit_events` RULEs silently swallow UPDATE and DELETE, `oauth_states(state)` PK rejects duplicates — 5 tests in `tests/integration/test_migrations.py` — 2026-04-15

---

## Phase 4 — Infrastructure Implementations

### ORM Models

- [x] Implement SQLAlchemy 2.0 ORM models in `infrastructure/persistence/models/orm.py`: `UserORM`, `SessionORM`, `WorkspaceORM`, `WorkspaceMembershipORM`, `AuditEventORM`, `OAuthStateORM`. Separate from domain entities. `__init__.py` empty per CLAUDE.md. — 2026-04-15

### Repository Implementations

- [x] [RED+GREEN] `UserRepositoryImpl` — upsert via `INSERT ... ON CONFLICT (google_sub) DO UPDATE RETURNING`, get by id/sub/email, email normalized lowercase. 5 integration tests. — 2026-04-15
- [x] [RED+GREEN] `SessionRepositoryImpl` — create, get by token_hash, revoke (idempotent via `revoked_at IS NULL` guard), delete_expired returns count. INET mapped to str. 5 integration tests. — 2026-04-15
- [x] [RED+GREEN] `WorkspaceRepositoryImpl` — create, get by id/slug, slug_exists; duplicate slug surfaces as UNIQUE violation (slug retry logic lives in the bootstrap service, not the repo). 4 integration tests. — 2026-04-15
- [x] [RED+GREEN] `WorkspaceMembershipRepositoryImpl` — create, get_by_user_id (all states), get_active_by_user_id, get_default_for_user (active+default only); UNIQUE(workspace_id,user_id) enforced. 5 integration tests. — 2026-04-15

### External Adapters

- [x] [RED+GREEN] `GoogleOAuthAdapter` — `get_authorization_url` with PKCE S256; `exchange_code` hits `/token` then `/tokeninfo` for `aud` + `email_verified` checks; typed `OAuthExchangeError`. Tests use `httpx.MockTransport` (no real network). 5 unit tests. — 2026-04-15
- [x] [RED+GREEN] `JwtAdapter` — HS256 encode/decode, typed `TokenExpiredError` + `TokenInvalidError`, `require_exp` enforced at decode, secret length ≥32 bytes. 7 unit tests including real sleep past expiry. — 2026-04-15
- [x] [RED+GREEN] `OAuthStateRepositoryImpl` — atomic `DELETE ... RETURNING verifier WHERE state=:s AND expires_at > now()` for single-use consume; `cleanup_expired` sweep; duplicate state PK violation. 6 integration tests. — 2026-04-15

### Acceptance Criteria — Phase 4

WHEN `UserRepositoryImpl.upsert()` is called with a new `google_sub`
THEN a row is inserted; returned `User.id` is a UUID; no exception raised

WHEN `UserRepositoryImpl.upsert()` is called with an existing `google_sub` but a different `email`
THEN the existing row is updated; `id` unchanged; `updated_at` refreshed

WHEN two concurrent `upsert()` calls for the same `google_sub` arrive simultaneously
THEN exactly one row exists after both complete (DB `ON CONFLICT DO UPDATE` is atomic)

WHEN `SessionRepositoryImpl.delete_expired()` is called
THEN only rows where `expires_at < NOW()` are deleted; active sessions untouched
AND the integer count of deleted rows is returned

WHEN `GoogleOAuthAdapter.exchange_code()` receives a non-2xx response from Google
THEN it raises `OAuthExchangeError` with the upstream HTTP status in the message

WHEN `JwtAdapter.decode()` receives a token signed with a different secret
THEN it raises `TokenInvalidError` (not a generic exception)

WHEN `OAuthStateRepositoryImpl.consume()` is called for a row whose `expires_at < now()`
THEN it returns `None` (not raises)
AND the expired row may or may not still exist (cleanup job handles sweep)

WHEN `OAuthStateRepositoryImpl.consume()` is called twice for the same state (e.g., duplicate callback)
THEN the first call returns the verifier and deletes the row
AND the second call returns `None`

---

## Phase 5 — Application Services

- [x] [RED+GREEN] `AuditService` — fire-and-forget wrapper (catches all, logs at ERROR, never raises). 6 unit tests with `FakeAuditRepository(explode=True)`. — 2026-04-15
- [x] [RED+GREEN] `SuperadminSeedService` — idempotent, case-insensitive seeded email match, emits `superadmin_seeded` audit event. 5 unit tests. — 2026-04-15
- [x] [RED+GREEN] `MembershipResolverService` — pure routing: 0→no_access / 1→single / N→picker; respects `last_chosen_workspace_id` only if it's in the active set. 6 unit tests. — 2026-04-15
- [x] [RED+GREEN] `AuthService` — `initiate_oauth` (state+PKCE+Google URL), `handle_callback` (consume state → exchange code → upsert user → seed superadmin → resolve memberships → issue JWT+refresh + audit), `refresh_token` (reject revoked/expired), `logout` (revoke + audit). 15 unit tests with all-fake collaborators. — 2026-04-15
- [x] [REFACTOR] `AuthService` — no ORM imports, no HTTP handling. `AUTH_ACCESS_TOKEN_TTL_SECONDS` / `AUTH_REFRESH_TOKEN_TTL_SECONDS` / `AUTH_OAUTH_STATE_TTL_SECONDS` + `AUTH_GOOGLE_REDIRECT_URI` added to `AuthSettings`. — 2026-04-15
- [x] Bugfix: `configure_logging` no longer clears caplog / third-party handlers (only strips prior `JsonFormatter`); Alembic `env.py` passes `disable_existing_loggers=False` so migrations don't mute app loggers in the pytest session. — 2026-04-15

### Acceptance Criteria — Phase 5

See also: specs/auth/spec.md (US-001, US-003), specs/bootstrap/spec.md

WHEN `AuthService.initiate_oauth()` is called
THEN it returns a URL containing `accounts.google.com` and `code_challenge_method=S256`
AND exactly one row exists in `oauth_states` for the generated `state` with `expires_at - now() ≈ 300s`

WHEN `AuthService.handle_callback()` is called with a `state` value that does not exist in `oauth_states` (or was already consumed)
THEN it raises `InvalidStateError` (not a generic exception)
AND no user record is created or modified

WHEN `AuthService.handle_callback()` is called for a user with 0 active memberships
THEN it raises `NoWorkspaceAccessError`
AND the controller redirects to `/login?error=no_workspace`
AND no JWT is issued, no session row is created

WHEN `AuthService.handle_callback()` is called for a user with exactly 1 active membership
THEN the callback result contains that workspace
AND no workspace or membership is created

WHEN `AuthService.handle_callback()` is called for a user with N active memberships and no valid last-chosen
THEN the callback result indicates `needs_picker=true` with the membership list
AND the controller redirects to `/workspace/select`

WHEN `AuthService.refresh_token()` is called with a revoked refresh token
THEN it raises `SessionRevokedError`
AND both cookies must be cleared by the caller (service does not set cookies)

WHEN `AuditService.log_event()` raises an internal DB exception
THEN the exception is swallowed and logged at ERROR level
AND the calling code is NOT affected (fire-and-forget contract)

WHEN `SuperadminSeedService.on_user_created()` runs for a user whose email matches `SEED_SUPERADMIN_EMAILS`
THEN the user's `is_superadmin` is set to true
AND an audit event `superadmin_seeded` is written

---

## Phase 6 — Auth Middleware

- [x] [RED] Write unit tests for `AuthMiddleware`: valid JWT injects `CurrentUser`, expired → 401 `TOKEN_EXPIRED`, missing → 401 `MISSING_TOKEN`, tampered → 401 `INVALID_TOKEN`, foreign-secret → `INVALID_TOKEN`, nullable `workspace_id`, malformed `sub` — 6 tests in `tests/unit/presentation/test_auth_middleware.py` — 2026-04-15
- [x] [GREEN] Implement `presentation/middleware/auth_middleware.py` — FastAPI dependency that verifies `access_token` cookie and injects `CurrentUser` into request — 2026-04-15
- [x] [GREEN] Implement `CurrentUser` Pydantic model with `id`, `email`, `workspace_id` (nullable for pre-picker flow) — 2026-04-15

**Status: COMPLETED** (2026-04-15)

### Acceptance Criteria — Phase 6

See also: specs/auth/spec.md (US-003)

WHEN a request arrives with a valid `access_token` cookie containing `sub`, `email`, `workspace_id`
THEN the middleware injects a `CurrentUser` with those values into the request state
AND the handler receives the object without an extra DB call

WHEN a request arrives with an `access_token` cookie whose `exp` claim is in the past
THEN the middleware returns `HTTP 401 { "error": { "code": "TOKEN_EXPIRED" } }`
AND the `WWW-Authenticate` header is NOT set (cookies, not Bearer)

WHEN a request arrives with no `access_token` cookie
THEN the middleware returns `HTTP 401 { "error": { "code": "MISSING_TOKEN" } }`

WHEN a request arrives with a JWT signed by a different secret (tampered)
THEN the middleware returns `HTTP 401 { "error": { "code": "INVALID_TOKEN" } }`
AND the event is logged at WARN with the first 8 chars of the token only (never full token)

---

## Phase 7 — Controllers

- [x] [RED+GREEN] Integration tests for 5 auth routes: initiate, callback (happy + cancelled + invalid_state + no_workspace), `/me` (auth + unauth), `/logout` (with + without cookies), `/refresh` (valid + missing + unknown) — 12 tests in `tests/integration/test_auth_controller.py` — 2026-04-15
- [x] [GREEN] Implement `presentation/controllers/auth.py` with all 5 routes; DI via `presentation/dependencies.py` — 2026-04-15
- [x] Register router under `/api/v1/auth` in `app/main.py` — 2026-04-15
- [x] [REFACTOR] Controllers are thin delegators — no business logic; parse cookies/query, call `AuthService`, format response — 2026-04-15
- [x] Fix: `database.py` now defers `get_settings` import so test monkeypatch of `app.config.settings.get_settings` takes effect; previously the lru_cache binding captured at import time sent test traffic to the dev Postgres on port 17000. — 2026-04-15

**Status: COMPLETED** (2026-04-15)

### Acceptance Criteria — Phase 7

See also: specs/auth/spec.md (US-001, US-003), specs/bootstrap/spec.md

**GET /api/v1/auth/google**
WHEN called without any params
THEN response is HTTP 302
AND `Location` header value contains `accounts.google.com/o/oauth2/v2/auth`
AND query string contains `code_challenge_method=S256`, `state`, `scope=openid%20email%20profile`

**GET /api/v1/auth/google/callback (happy path)**
WHEN called with valid `code` and matching `state` (mocked Google token exchange returns valid ID token)
THEN response is HTTP 302 to `/workspace/{slug}`
AND `Set-Cookie` contains `access_token` (HttpOnly, Secure, SameSite=Lax, Max-Age=900)
AND `Set-Cookie` contains `refresh_token` (HttpOnly, Secure, SameSite=Lax, Max-Age=2592000, Path=/api/v1/auth/refresh)

**GET /api/v1/auth/google/callback (state mismatch)**
WHEN called with a `state` value not present in `oauth_states` (or already consumed)
THEN response is HTTP 302 to `/login?error=invalid_state`
AND no cookies are set

**GET /api/v1/auth/google/callback (Google returns error=access_denied)**
THEN response is HTTP 302 to `/login?error=cancelled`

**POST /api/v1/auth/refresh**
WHEN called with a valid `refresh_token` cookie
THEN response is HTTP 200
AND `Set-Cookie` contains new `access_token`
AND body is `{ "data": { "access_token_expires_at": "ISO8601" } }`

WHEN called with expired or revoked `refresh_token`
THEN response is HTTP 401 with `{ "error": { "code": "SESSION_EXPIRED" } }`
AND both cookies are cleared (Max-Age=0)

**POST /api/v1/auth/logout**
WHEN called with valid `access_token` cookie
THEN response is HTTP 204 with no body
AND both `access_token` and `refresh_token` cookies have `Max-Age=0`
AND `sessions.revoked_at` is set in DB

**GET /api/v1/auth/me**
WHEN called with valid `access_token`
THEN response is HTTP 200
AND body matches `{ "data": { "id", "email", "full_name", "avatar_url", "workspace_id", "workspace_slug", "is_superadmin" } }`

WHEN called without `access_token`
THEN response is HTTP 401 with `{ "error": { "code": "MISSING_TOKEN" } }`

---

## Phase 8 — Rate Limiting

- [x] Add `slowapi` in-memory Limiter keyed off `X-Forwarded-For` (leftmost) with socket fallback; per-route decorator `@auth_limiter.limit(AUTH_LIMIT)` on all 5 auth routes; global exception handler returns envelope `{error:{code:"TOO_MANY_REQUESTS",...}}` with `Retry-After` header (expiry computed from `exc.limit.limit.get_expiry()`). `AUTH_RATE_LIMIT_PER_MINUTE=10` added to `AuthSettings`. — 2026-04-15
- [x] [RED+GREEN] 4 integration tests in `tests/integration/test_rate_limiting.py`: first 10 allowed, 11th returns 429 + `Retry-After`, per-IP isolation works, non-auth endpoints (`/api/v1/health`) untouched. — 2026-04-15

**Status: COMPLETED** (2026-04-15)

### Acceptance Criteria — Phase 8

WHEN 10 requests to any `/api/v1/auth/*` endpoint arrive from the same IP within 60 seconds
THEN all 10 return the expected response (2xx or 3xx)

WHEN the 11th request arrives from the same IP within the same 60-second window
THEN response is HTTP 429 `{ "error": { "code": "TOO_MANY_REQUESTS", "message": "Rate limit exceeded" } }`
AND `Retry-After` header is set to the seconds remaining in the window

WHEN a new 60-second window starts (previous window expired)
THEN requests are allowed again from that IP

---

## Phase 9 — Session Cleanup (Background Job)

- [x] [RED+GREEN] `cleanup_expired_sessions` — Celery task in `app/infrastructure/jobs/session_cleanup.py`; deletes only `expires_at < NOW()`; returns deleted count. Runs in a dedicated thread with its own event loop so it's callable from both sync Celery workers and pytest-asyncio contexts. 2 integration tests in `tests/integration/test_session_cleanup_job.py`. — 2026-04-15
- [x] Registered in Celery Beat schedule: `cleanup-expired-sessions-daily` at 03:15 UTC via `crontab(hour=3, minute=15)`. — 2026-04-15
- [x] [RED+GREEN] `cleanup_expired_oauth_states` — Celery task in `app/infrastructure/jobs/oauth_state_cleanup.py`; same thread/loop pattern. 2 integration tests in `tests/integration/test_oauth_state_cleanup_job.py`. — 2026-04-15
- [x] Registered in Celery Beat schedule: `cleanup-expired-oauth-states-every-10m` via `crontab(minute="*/10")`. `autodiscover_tasks(["app.infrastructure.jobs"])` added to Celery app. — 2026-04-15

**Status: COMPLETED** (2026-04-15)

### Acceptance Criteria — Phase 9

WHEN `cleanup_expired_sessions` runs against a DB containing: 2 expired sessions, 1 revoked session older than TTL, 3 active sessions
THEN the 3 active sessions remain untouched
AND the expired + revoked-past-TTL rows are deleted
AND the task returns the count of deleted rows as an integer

WHEN `cleanup_expired_sessions` runs on an empty DB (no sessions at all)
THEN no exception is raised and it returns 0

---

## Phase 10 — Global Error Middleware

- [x] `app/presentation/middleware/error_middleware.py` — `register_error_handlers(app)` wires exception-to-envelope mapping. — 2026-04-15
- [x] Mapping: `SessionExpiredError → 401 SESSION_EXPIRED`, `SessionRevokedError → 401 SESSION_REVOKED`, `InvalidStateError → 400 INVALID_OAUTH_STATE`, `NoWorkspaceAccessError → 403 NO_WORKSPACE`, `OAuthExchangeError → 502 OAUTH_EXCHANGE_FAILED`, `RequestValidationError → 422 VALIDATION_ERROR`. `StarletteHTTPException` handler passes through controller envelopes and wraps plain-string details. — 2026-04-15
- [x] Catch-all `Exception` handler logs full traceback via `logger.exception`, returns `500 INTERNAL_ERROR` with generic message (no internal detail leaked). — 2026-04-15
- [x] 6 unit tests in `tests/unit/presentation/test_error_middleware.py` covering every mapping + generic 500 (uses throwaway FastAPI app + `ASGITransport(raise_app_exceptions=False)` so unhandled exceptions surface as 500). — 2026-04-15
- [x] Breaking change for consistency: HTTPException responses from controllers now render as `{"error":{...}}` (flat envelope), not `{"detail":{"error":{...}}}`. Updated `test_me_unauthenticated_returns_401` + `test_refresh_without_cookie_returns_401` accordingly. — 2026-04-15

**Status: COMPLETED** (2026-04-15)

---

## Definition of Done

- [x] All unit and integration tests pass — 189/189 on 2026-04-15
- [ ] `mypy --strict` clean on all EP-00 modules — not re-run after Phase 8-10 changes
- [x] `ruff check` clean on Phase 8-10 modules (`rate_limit.py`, `error_middleware.py`, `jobs/`, `main.py`); pre-existing `B008` warnings in `dependencies.py` are unrelated to EP-00 and tracked separately
- [x] All 5 auth endpoints respond correctly to happy path and documented error cases — covered by `tests/integration/test_auth_controller.py` (12 tests)
- [x] `audit_events` table has entries with `category='auth'` — AuthService emits events on login/logout/failed auth; verified indirectly via `test_auth_controller` green
- [x] Rate limiting tested and confirmed at 429 on 11th request — `tests/integration/test_rate_limiting.py`

---

## Phase 11 — Post-review hardening (2026-04-15)

### Security / Correctness

- [x] **#1 IDOR on /auth/refresh** — `AuthService.refresh_token` now validates workspace_id against user's active memberships via `MembershipResolverService._repo.get_active_by_user_id`. Raises `NoWorkspaceAccessError` on non-member workspace. Tests: `test_refresh_token_idor_rejects_non_member_workspace`. — 2026-04-15
- [x] **#2 Open redirect via return_to** — `_safe_return_to(value)` helper in `auth.py` blocks `//evil.com`, `/\evil.com`, `://` schemes, `@` in path. Applied on `/google` initiate and in callback. 14 parametrized tests in `test_safe_return_to.py`. — 2026-04-15
- [x] **#3 email_verified fail-open** — `google_oauth_adapter.py` defaults `email_verified` to `"false"` when absent. Accepts both `bool True` and string `"true"`. Tests: `test_email_verified_missing_defaults_to_rejected`, `test_email_verified_bool_true_accepted`. — 2026-04-15
- [x] **#4 Google token validation** — validates `iss in {accounts.google.com, https://accounts.google.com}`, `aud == client_id`, `exp > now()`. Raises `OAuthExchangeError("invalid_id_token:...")`. Tests: missing iss, wrong iss, expired exp, wrong aud. — 2026-04-15
- [x] **#5 Email validation bypass** — added `User.update_email(new_email)` that routes through `_validate_email`. `AuthService.handle_callback` uses it instead of direct attribute assignment. — 2026-04-15
- [x] **#6+7 return_to + last_chosen_workspace_id via state row** — `IOAuthStateRepository.create/consume` updated with new params; returns `ConsumedOAuthState` dataclass. `AuthService.initiate_oauth` persists both; `handle_callback` reads from consumed state. Callback no longer reads from query params. `CallbackResult` carries `return_to`. Tests: round-trip, callback ignores client-supplied workspace. — 2026-04-15
- [x] **#8 Refresh rechecks user status** — `refresh_token` rejects `user.status != 'active'` with `UserSuspendedError` (→ 401). Tests: suspended user → 401, deleted user → 401. — 2026-04-15
- [x] **#9 No JWT bytes in logs** — `auth_middleware.py` logs `type(exc).__name__` only on decode failure, not first 8 chars of token. — 2026-04-15

### DB Migration 0007_hardening

- [x] **#11 audit_events RULEs → BEFORE triggers** — silent RULE behavior replaced by `audit_events_block_mutation()` trigger that raises. Tests: `test_audit_events_update_raises`, `test_audit_events_delete_raises`. — 2026-04-15
- [x] **#12 audit_events FKs ON DELETE SET NULL** — `actor_id` and `workspace_id` FKs recreated with `ON DELETE SET NULL`. ORM updated. — 2026-04-15
- [x] **#13 workspaces.created_by ON DELETE RESTRICT** — FK recreated with explicit `ON DELETE RESTRICT`. ORM updated. — 2026-04-15
- [x] **#14 Partial unique index** — `uq_default_active_membership_per_user` on `workspace_memberships (user_id) WHERE is_default AND state='active'`. Test: `test_one_active_default_membership_per_user`. — 2026-04-15
- [x] **#15 Email case-insensitive uniqueness** — dropped `users_email_key`, added `uq_users_email_lower ON users (lower(email))`. Test: `test_email_case_insensitive_uniqueness`. — 2026-04-15
- [x] **oauth_states length cap** — `state` and `verifier` columns → `varchar(128)`. New columns `return_to TEXT`, `last_chosen_workspace_id UUID`. — 2026-04-15

### Should Fix

- [x] **Slug TOCTOU** — `WorkspaceRepositoryImpl.create` catches `IntegrityError` on slug UNIQUE, raises `WorkspaceSlugConflictError`. — 2026-04-15
- [x] **Engine pool hygiene** — `pool_pre_ping=True, pool_recycle=1800` added to `create_async_engine`. — 2026-04-15
- [x] **Session lookup hardening** — `get_by_token_hash` filters `revoked_at IS NULL AND expires_at > now()` at DB level. — 2026-04-15
- [x] **Cookie clear attrs** — `_clear_cookies` and logout handlers pass `httponly=True, secure=<from_scheme>, samesite='lax'` and correct path. — 2026-04-15
- [x] **CORS sanity check** — `create_app` raises `RuntimeError` at startup if `"*"` in `cors_allowed_origins` with `allow_credentials=True`. — 2026-04-15
- [x] **Upsert email conflict** — `UserRepositoryImpl.upsert` catches `IntegrityError` on email unique, raises `EmailAlreadyLinkedError`. — 2026-04-15

**Status: COMPLETED** (2026-04-15)

---

## Phase 11 Round 2 — Post-review hardening (2026-04-15)

### Should Fix

- [x] **A. JWT iss/aud enforcement** — `JwtAdapter.__init__` takes `issuer`/`audience` params (defaults `"wmp"`/`"wmp-web"`). `encode` stamps both; `decode` verifies via `jose.jwt.decode(audience=..., issuer=...)`. `AuthSettings` gets `jwt_issuer`/`jwt_audience`. `dependencies.py` wires them in. New tests: wrong iss raises, wrong aud raises, roundtrip stamps claims, custom iss/aud. — 2026-04-15
- [x] **B. OAuth state collision guard** — `OAuthStateRepositoryImpl.create` catches `IntegrityError` and raises typed `OAuthStateCollisionError` (defined in domain `oauth_state_repository.py`). Error middleware maps it to 500 `INTERNAL_ERROR`. Updated existing duplicate-state test to assert typed exception. — 2026-04-15
- [x] **C. AuditService UUID cleanup** — replaced `AuditEvent.auth(action="_placeholder").id` with `uuid4()`. — 2026-04-15
- [x] **D. Error middleware `_register` helper** — factored `def _register(app, exc_type, handler)` with single `# type: ignore[arg-type]`. `register_error_handlers` calls it for all mapped types. — 2026-04-15
- [x] **E. Controller mislabel fix** — `google_callback`: missing `state` → `/login?error=invalid_state`; state present but missing `code` → `/login?error=oauth_failed`. Added integration tests for both cases. — 2026-04-15
- [x] **F. Refresh IDOR integration test** — `test_refresh_idor_wrong_workspace_returns_401`: seed alice in W1, seed bob in W2, login as alice, refresh with W2 slug → 401 `NO_WORKSPACE_ACCESS`. — 2026-04-15

### Nitpicks

- [x] **G. Dead wrappers verified** — `decode_access_token` kept (used in test); `raw_token_not_stored()` kept (invariant marker, used in test); `build_limiter` kept (documented intentional). — 2026-04-15
- [x] **H. `_COMPOUND_SLDS` comment** — note added: hand-rolled list doesn't cover PSL edge cases like `foo.com.br`; `tldextract` as upgrade path. — 2026-04-15

### DB Review

- [x] **I. ORM composite index order** — `AuditEventORM` indexes use `sa.text("created_at DESC")` to match migration 0005. — 2026-04-15
- [x] **J/K/L. Migration 0008_indexes** — partial `idx_sessions_user_active (user_id, expires_at DESC) WHERE revoked_at IS NULL`; composite `idx_workspace_memberships_user_state (user_id, state)` replacing user_id-only; dropped `idx_audit_events_category` (no read path). ORM updated. Roundtrip: upgrade→downgrade→upgrade clean. — 2026-04-15
- [x] **M. ORM JSONB server_default** — `AuditEventORM.context server_default` → `sa.text("'{}'::jsonb")` to match migration. — 2026-04-15
- [x] **N. `entity_id` polymorphic comment** — added inline `# no FK — polymorphic reference across entities`. — 2026-04-15
- [x] **O. pgcrypto downgrade doc** — comment in `0001_create_users.py` downgrade() explains why DROP EXTENSION is absent. — 2026-04-15

**Tests: 220 → 227 (+7 new, 0 regressions)**

**Status: COMPLETED** (2026-04-15)
