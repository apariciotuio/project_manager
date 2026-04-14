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

- [ ] Create `backend/` directory structure: `presentation/controllers/`, `application/services/`, `domain/models/`, `domain/repositories/`, `infrastructure/persistence/`, `infrastructure/adapters/`, `infrastructure/jobs/`
- [ ] Add Python dependencies: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `python-jose[cryptography]`, `httpx`, `redis[asyncio]`, `python-multipart`, `pydantic-settings`, `celery`
- [ ] Configure environment variables in `.env.example`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `JWT_SECRET`, `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_TTL=900`, `REFRESH_TOKEN_TTL=2592000`, `REDIS_URL`, `DATABASE_URL`, `SEED_SUPERADMIN_EMAILS` (comma-separated)
- [ ] Configure `alembic.ini` and `env.py` for async SQLAlchemy engine
- [ ] Configure pytest with `pytest-asyncio`, test DB fixture using `asyncpg`

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

- [ ] [RED] Write unit tests for `User` entity: `from_google_claims()` factory sets all fields, `update_from_google()` merges name/avatar, email validation rejects invalid formats
- [ ] [GREEN] Implement `domain/models/user.py` — `User` dataclass (no ORM decorators), fields: `id`, `google_sub`, `email`, `full_name`, `avatar_url`, `status`, `created_at`, `updated_at`
- [ ] [REFACTOR] Verify `User` has zero imports from infrastructure or application layers

### Session Entity

- [ ] [RED] Write unit tests for `Session` entity: `is_expired()` returns True when `expires_at < now()`, `is_revoked()` returns True when `revoked_at` is set, `token_hash` is SHA-256 of opaque token
- [ ] [GREEN] Implement `domain/models/session.py` — `Session` entity

### Workspace Entity

- [ ] [RED] Write unit tests for `Workspace` entity: slug generation from email domain, `derive_name_from_domain()` strips `@` and TLD, public provider detection (gmail, yahoo, etc.) returns generic slug
- [ ] [GREEN] Implement `domain/models/workspace.py` — `Workspace` entity
- [ ] [GREEN] Implement `domain/models/workspace_membership.py` — `WorkspaceMembership` entity (fields: `id`, `workspace_id`, `user_id`, `role`, `is_default`, `joined_at`)

- [ ] [REFACTOR] Review all domain models: no ORM imports, no HTTP concerns, pure dataclasses

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

- [ ] Implement `domain/repositories/user_repository.py` — `IUserRepository` ABC: `get_by_id(id) -> User | None`, `get_by_google_sub(sub) -> User | None`, `get_by_email(email) -> User | None`, `upsert(user) -> User`
- [ ] Implement `domain/repositories/session_repository.py` — `ISessionRepository` ABC: `create(session) -> Session`, `get_by_token_hash(hash) -> Session | None`, `revoke(session_id) -> None`, `delete_expired() -> int`
- [ ] Implement `domain/repositories/workspace_repository.py` — `IWorkspaceRepository` ABC: `create(workspace) -> Workspace`, `get_by_id(id) -> Workspace | None`, `get_by_slug(slug) -> Workspace | None`, `slug_exists(slug) -> bool`
- [ ] Implement `domain/repositories/workspace_membership_repository.py` — `IWorkspaceMembershipRepository` ABC: `create(membership) -> WorkspaceMembership`, `get_by_user_id(user_id) -> list[WorkspaceMembership]`, `get_default_for_user(user_id) -> WorkspaceMembership | None`

### Acceptance Criteria — Phase 2

WHEN any repository method is called on a concrete implementation that is not yet injected
THEN Python raises `TypeError` at construction time (interfaces are uninstantiable ABCs)

WHEN `IUserRepository.upsert()` is called with the same `google_sub` twice
THEN the second call updates the existing record (no duplicate row)
AND the returned `User` has the same `id` as the first call

---

## Phase 3 — Database Migrations

- [ ] Create Alembic migration `001_create_users`: table with `id`, `google_sub`, `email`, `full_name`, `avatar_url`, `status`, `created_at`, `updated_at`; indexes on `google_sub` and `email`
- [ ] Create Alembic migration `002_create_sessions`: table with `id`, `user_id FK`, `token_hash`, `expires_at`, `revoked_at`, `created_at`, `ip_address`, `user_agent`; indexes on `user_id`, `token_hash`, `expires_at`
- [ ] Create Alembic migration `003_create_workspaces`: table with `id`, `name`, `slug`, `created_by FK`, `status`, `created_at`, `updated_at`; unique index on `slug`
- [ ] Create Alembic migration `004_create_workspace_memberships`: table with `id`, `workspace_id FK`, `user_id FK`, `role` (display label), `state` CHECK ('invited','active','suspended','deleted'), `is_default`, `joined_at`; UNIQUE `(workspace_id, user_id)`; index on `user_id` + composite `(workspace_id, state)`
- [ ] Create Alembic migration `005_create_audit_events`: unified append-only table per design.md §audit_events (`id`, `category`, `action`, `actor_id FK nullable`, `workspace_id FK nullable`, `entity_type`, `entity_id`, `ip_address`, `user_agent`, `outcome`, `details JSONB`, `created_at`); indexes per design.md; PostgreSQL RULEs `no_update_audit`, `no_delete_audit`. Auth events use `category='auth'`; admin/domain events written by EP-10 use other categories. Do NOT create a separate `audit_logs` table.
- [ ] Verify all migrations apply and roll back cleanly against local dev DB

---

## Phase 4 — Infrastructure Implementations

### ORM Models

- [ ] Implement SQLAlchemy ORM models (separate from domain entities): `UserORM`, `SessionORM`, `WorkspaceORM`, `WorkspaceMembershipORM`, `AuditLogORM` in `infrastructure/persistence/models/`

### Repository Implementations

- [ ] [RED] Write integration tests for `UserRepositoryImpl` against test DB: upsert new user, upsert existing user (same `google_sub`), conflict on email raises correctly
- [ ] [GREEN] Implement `infrastructure/persistence/user_repo_impl.py` with mapper `UserORM ↔ User`
- [ ] [RED] Write integration tests for `SessionRepositoryImpl`: create, get by hash, revoke sets `revoked_at`, delete_expired removes only expired rows
- [ ] [GREEN] Implement `infrastructure/persistence/session_repo_impl.py`
- [ ] [RED] Write integration tests for `WorkspaceRepositoryImpl`: create with slug, get by slug, slug uniqueness retry on collision
- [ ] [GREEN] Implement `infrastructure/persistence/workspace_repo_impl.py`
- [ ] [GREEN] Implement `infrastructure/persistence/workspace_membership_repo_impl.py`

### External Adapters

- [ ] [RED] Write unit tests for `GoogleOAuthAdapter` using `httpx` mock (no real Google calls): `get_authorization_url()` returns URL with correct params, `exchange_code()` returns `GoogleClaims` dataclass on valid response, HTTP error from Google raises `OAuthExchangeError`
- [ ] [GREEN] Implement `infrastructure/adapters/google_oauth_adapter.py` — interface: `get_authorization_url(state, challenge) -> str`, `exchange_code(code, verifier) -> GoogleClaims`
- [ ] [RED] Write unit tests for `JwtAdapter`: encode/decode round-trip, expired token raises `TokenExpiredError`, tampered signature raises `TokenInvalidError`
- [ ] [GREEN] Implement `infrastructure/adapters/jwt_adapter.py` — `encode(payload) -> str`, `decode(token) -> dict`
- [ ] [GREEN] Implement `infrastructure/adapters/redis_adapter.py` — `set_oauth_state(state, verifier, ttl)`, `get_oauth_state(state) -> str | None`, `delete_oauth_state(state)`

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

WHEN `RedisAdapter.get_oauth_state()` is called with a key that has expired
THEN it returns `None` (not raises)

---

## Phase 5 — Application Services

- [ ] [RED] Write unit tests for `AuthService.initiate_oauth()`: returns valid redirect URL, state stored in Redis with 5-min TTL, PKCE challenge is S256 of verifier
- [ ] [RED] Write unit tests for `AuthService.handle_callback()`: happy path returns `(User, active_memberships[])`; state mismatch raises `InvalidStateError`; state expired raises `StateExpiredError`; Google exchange fails raises `OAuthExchangeError`; user with 0 memberships → `NoWorkspaceAccessError`; user with 1 → routes to that workspace; user with N → returns `needs_picker=true` with list; `returnTo` deeplink preserved across redirect
- [ ] [RED] Write unit tests for `AuthService.refresh_token()`: valid refresh token returns new JWT, expired refresh raises `SessionExpiredError`, revoked refresh raises `SessionRevokedError`
- [ ] [RED] Write unit tests for `AuthService.logout()`: session revoked in DB, audit log entry written with `logout` event type
- [ ] [GREEN] Implement `application/services/auth_service.py` — no ORM imports, injected repository interfaces
- [ ] [RED] Write unit tests for `MembershipResolverService.resolve(user_id)`: returns `ResolverOutcome.no_access` when user has 0 active memberships; returns `ResolverOutcome.single(workspace)` when exactly 1; returns `ResolverOutcome.picker(memberships[])` when N; respects `last_chosen_workspace_id` if valid and still active
- [ ] [GREEN] Implement `application/services/membership_resolver_service.py`
- [ ] [RED] Write unit tests for `SuperadminSeedService.on_user_created(user)`: if `user.email` in `SEED_SUPERADMIN_EMAILS` → sets `is_superadmin=true` and writes audit event `superadmin_seeded`; otherwise no-op
- [ ] [GREEN] Implement `application/services/superadmin_seed_service.py`
- [ ] [GREEN] Implement `application/services/audit_service.py` — `log_event(event_type, user_id, ip, user_agent, outcome, details)` — fire-and-forget, swallows all exceptions with error log (never raises to caller)
- [ ] [REFACTOR] AuthService and BootstrapService: verify no ORM imports, no HTTP handling, pure orchestration via injected interfaces

### Acceptance Criteria — Phase 5

See also: specs/auth/spec.md (US-001, US-003), specs/bootstrap/spec.md

WHEN `AuthService.initiate_oauth()` is called
THEN it returns a URL containing `accounts.google.com` and `code_challenge_method=S256`
AND the Redis key for `state` has a TTL of exactly 300 seconds (5 min)

WHEN `AuthService.handle_callback()` is called with a `state` value that does not exist in Redis
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

- [ ] [RED] Write unit tests for `AuthMiddleware`: valid JWT in cookie passes and injects `CurrentUser`, expired JWT returns 401 with `TOKEN_EXPIRED` code, missing cookie returns 401 with `MISSING_TOKEN` code, tampered JWT signature returns 401 with `INVALID_TOKEN` code
- [ ] [GREEN] Implement `presentation/middleware/auth_middleware.py` — FastAPI dependency that verifies `access_token` cookie and injects `CurrentUser` typed object into request state
- [ ] [GREEN] Implement `CurrentUser` Pydantic model: `id: UUID`, `email: str`, `workspace_id: UUID`

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

- [ ] [RED] Write integration tests for `GET /api/v1/auth/google`: returns 302, `Location` header contains `accounts.google.com`, state and verifier stored in Redis
- [ ] [RED] Write integration tests for `GET /api/v1/auth/google/callback`: happy path (mock Google + DB) sets two cookies and redirects according to membership resolution (0 → `/login?error=no_workspace`, 1 → `/workspace/{slug}`, N → `/workspace/select`); state mismatch returns 400; state expired returns 400; `returnTo` deeplink preserved when valid
- [ ] [RED] Write integration tests for `POST /api/v1/auth/refresh`: valid refresh token returns 200 + new `access_token` cookie, expired token returns 401, revoked token returns 401
- [ ] [RED] Write integration tests for `POST /api/v1/auth/logout`: session revoked in DB, both cookies cleared (Max-Age=0), response is 204
- [ ] [RED] Write integration tests for `GET /api/v1/auth/me`: authenticated returns `{ data: { id, email, full_name, avatar_url, workspace_id, workspace_slug } }`, unauthenticated returns 401
- [ ] [GREEN] Implement `presentation/controllers/auth_controller.py` with all 5 routes
- [ ] Register router on FastAPI app with prefix `/api/v1/auth`
- [ ] [REFACTOR] Controllers contain zero business logic — every route handler is a thin delegator to `AuthService`

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
WHEN called with a `state` value not present in Redis
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

- [ ] Add rate limiting using `slowapi` or custom Redis counter: 10 req/min per IP on `/api/v1/auth/*`
- [ ] [RED] Write test: 11th request in 1-minute window returns 429 `TOO_MANY_REQUESTS`
- [ ] [GREEN] Implement rate limiter middleware

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

- [ ] [RED] Write unit test for `cleanup_expired_sessions` task: only deletes rows where `expires_at < NOW()`, revoked rows older than TTL are removed, active sessions untouched
- [ ] [GREEN] Implement `infrastructure/jobs/session_cleanup.py` — Celery task
- [ ] Register task in Celery Beat schedule: daily execution

### Acceptance Criteria — Phase 9

WHEN `cleanup_expired_sessions` runs against a DB containing: 2 expired sessions, 1 revoked session older than TTL, 3 active sessions
THEN the 3 active sessions remain untouched
AND the expired + revoked-past-TTL rows are deleted
AND the task returns the count of deleted rows as an integer

WHEN `cleanup_expired_sessions` runs on an empty DB (no sessions at all)
THEN no exception is raised and it returns 0

---

## Phase 10 — Global Error Middleware

- [ ] Implement `presentation/middleware/error_middleware.py` — maps domain exceptions to HTTP responses
- [ ] Mapping table: `SessionExpiredError → 401 SESSION_EXPIRED`, `SessionRevokedError → 401 SESSION_REVOKED`, `InvalidStateError → 400 INVALID_OAUTH_STATE`, `OAuthExchangeError → 502 OAUTH_EXCHANGE_FAILED`
- [ ] Catch-all: unhandled exceptions return 500 with `INTERNAL_ERROR` code, log full traceback

---

## Definition of Done

- [ ] All unit and integration tests pass
- [ ] `mypy --strict` clean on all EP-00 modules
- [ ] `ruff check` and `ruff format` clean
- [ ] All 5 auth endpoints respond correctly to happy path and documented error cases
- [ ] `audit_events` table has entries with `category='auth'` for login, logout, and failed auth attempts in integration test run
- [ ] Rate limiting tested and confirmed at 429 on 11th request
