# EP-00 Implementation Checklist

**Status**: [ ] Not started

Refs: EP-00
Branch: `feature/ep-00-auth-identity-bootstrap`

---

## Phase 0 — Setup

- [ ] Create `backend/` directory structure per DDD layout (presentation, application, domain, infrastructure)
- [ ] Add Python dependencies: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `python-jose[cryptography]`, `httpx`, `redis[asyncio]`, `python-multipart`, `pydantic-settings`
- [ ] Configure environment variables: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `JWT_SECRET`, `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_TTL=900`, `REFRESH_TOKEN_TTL=2592000`, `REDIS_URL`, `DATABASE_URL`
- [ ] Configure `alembic.ini` and `env.py` for async SQLAlchemy
- [ ] Scaffold `frontend/` Next.js 14 App Router project with TypeScript
- [ ] Add frontend dependencies: `axios` (or `ky`), `zustand` (or `jotai`) for auth state

---

## Phase 1 — Domain Models (Backend)

> RED: Write failing tests first. GREEN: Implement. REFACTOR: Clean up.

- [ ] **[RED]** Write unit tests for `User` entity: creation, email validation, `from_google_claims()` factory method, `update_from_google()` method
- [ ] **[GREEN]** Implement `backend/domain/models/user.py` — `User` dataclass/entity (no ORM decorators)
- [ ] **[RED]** Write unit tests for `Session` entity: creation, `is_expired()`, `is_revoked()`, `token_hash` computation
- [ ] **[GREEN]** Implement `backend/domain/models/session.py` — `Session` entity
- [ ] **[RED]** Write unit tests for `Workspace` entity: creation, slug generation, `derive_name_from_domain()`, public provider detection
- [ ] **[GREEN]** Implement `backend/domain/models/workspace.py` — `Workspace` entity
- [ ] **[GREEN]** Implement `backend/domain/models/workspace_membership.py` — `WorkspaceMembership` entity
- [ ] **[REFACTOR]** Review all domain models for purity (no imports from infrastructure or application layers)

---

## Phase 2 — Repository Interfaces (Backend)

- [ ] Implement `backend/domain/repositories/user_repository.py` — `IUserRepository` interface (abstract base class): `get_by_id`, `get_by_google_sub`, `get_by_email`, `upsert`
- [ ] Implement `backend/domain/repositories/session_repository.py` — `ISessionRepository`: `create`, `get_by_token_hash`, `revoke`, `delete_expired`
- [ ] Implement `backend/domain/repositories/workspace_repository.py` — `IWorkspaceRepository`: `create`, `get_by_id`, `get_by_slug`, `slug_exists`
- [ ] Implement `backend/domain/repositories/workspace_membership_repository.py` — `IWorkspaceMembershipRepository`: `create`, `get_by_user_id`, `get_default_for_user`

---

## Phase 3 — DB Migrations

- [ ] Create Alembic migration: `users` table (see design.md schema)
- [ ] Create Alembic migration: `sessions` table
- [ ] Create Alembic migration: `workspaces` table
- [ ] Create Alembic migration: `workspace_memberships` table
- [ ] Create Alembic migration: `audit_logs` table
- [ ] Verify all indexes are included in migrations
- [ ] Run migrations against local dev DB, confirm clean schema

---

## Phase 4 — Infrastructure Implementations (Backend)

- [ ] Implement SQLAlchemy ORM models (separate from domain entities): `UserORM`, `SessionORM`, `WorkspaceORM`, `WorkspaceMembershipORM`, `AuditLogORM`
- [ ] Implement `backend/infrastructure/persistence/user_repo_impl.py` with mapper `UserORM <-> User`
- [ ] **[RED]** Write integration tests for `UserRepositoryImpl`: upsert (new user), upsert (existing user same sub), upsert conflict on email
- [ ] **[GREEN]** Implement `UserRepositoryImpl`
- [ ] Implement `SessionRepositoryImpl` with same RED/GREEN pattern
- [ ] Implement `WorkspaceRepositoryImpl` with slug uniqueness retry logic
- [ ] Implement `WorkspaceMembershipRepositoryImpl`
- [ ] Implement `backend/infrastructure/adapters/google_oauth_adapter.py` — wraps `httpx.AsyncClient` calls to Google token endpoint and JWKS verification. Interface: `exchange_code(code, verifier) -> GoogleClaims`, `get_authorization_url(state, challenge) -> str`
- [ ] **[RED]** Write unit tests for `GoogleOAuthAdapter` with `httpx` mock (not real Google calls)
- [ ] **[GREEN]** Implement `GoogleOAuthAdapter`
- [ ] Implement `backend/infrastructure/adapters/jwt_adapter.py` — `encode(payload) -> str`, `decode(token) -> dict` (raises on invalid/expired)
- [ ] **[RED]** Write unit tests for `JwtAdapter`: encode/decode round trip, expired token raises, tampered token raises
- [ ] **[GREEN]** Implement `JwtAdapter`
- [ ] Implement `backend/infrastructure/adapters/redis_adapter.py` — `set_oauth_state(state, verifier, ttl)`, `get_oauth_state(state) -> str | None`, `delete_oauth_state(state)`

---

## Phase 5 — Application Services (Backend)

- [ ] **[RED]** Write unit tests for `AuthService.initiate_oauth()`: returns valid redirect URL, state stored in Redis, PKCE challenge correct
- [ ] **[RED]** Write unit tests for `AuthService.handle_callback()`: happy path, state mismatch 400, state expired 400, Google exchange fails 502, new user created + workspace bootstrapped, returning user resolved
- [ ] **[RED]** Write unit tests for `AuthService.refresh_token()`: valid refresh returns new access token, expired refresh raises, revoked refresh raises
- [ ] **[RED]** Write unit tests for `AuthService.logout()`: session revoked, audit log written
- [ ] **[GREEN]** Implement `backend/application/services/auth_service.py`
- [ ] **[RED]** Write unit tests for `BootstrapService.bootstrap_workspace()`: new user → workspace created with admin membership, returning user → existing workspace returned, race condition handled (mock transaction), public email domain → generic name
- [ ] **[GREEN]** Implement `backend/application/services/bootstrap_service.py`
- [ ] **[REFACTOR]** AuthService and BootstrapService: no ORM imports, no HTTP details, pure business logic via injected interfaces
- [ ] Implement `backend/application/services/audit_service.py` — `log_event(event_type, user_id, ip, user_agent, outcome, details)` — fire-and-forget, must never raise

---

## Phase 6 — Auth Middleware (Backend)

- [ ] **[RED]** Write unit tests for `AuthMiddleware`: valid JWT passes, expired JWT returns 401, missing cookie returns 401, tampered JWT returns 401
- [ ] **[GREEN]** Implement `backend/presentation/middleware/auth_middleware.py` — FastAPI dependency or Starlette middleware that verifies `access_token` cookie and injects `CurrentUser` into request state
- [ ] Implement `CurrentUser` typed dependency for use in route handlers

---

## Phase 7 — Controllers (Backend)

- [ ] **[RED]** Write integration tests for `GET /api/v1/auth/google`: returns 302, Location header contains Google OAuth URL, state cookie/Redis key set
- [ ] **[RED]** Write integration tests for `GET /api/v1/auth/google/callback`: happy path (mock Google, DB), state mismatch, state expired, first login bootstrap, returning user
- [ ] **[RED]** Write integration tests for `POST /api/v1/auth/refresh`: valid refresh token, expired token, revoked token
- [ ] **[RED]** Write integration tests for `POST /api/v1/auth/logout`: session revoked, cookies cleared, 204 returned
- [ ] **[RED]** Write integration tests for `GET /api/v1/auth/me`: authenticated returns user + workspace, unauthenticated returns 401
- [ ] **[GREEN]** Implement `backend/presentation/controllers/auth_controller.py` with all 5 routes
- [ ] Register routes on FastAPI app with prefix `/api/v1/auth`
- [ ] **[REFACTOR]** Controllers must not contain business logic — delegate entirely to `AuthService`

---

## Phase 8 — Rate Limiting (Backend)

- [ ] Add rate limiting middleware using `slowapi` or custom Redis counter: 10 req/min per IP on `/api/v1/auth/*` endpoints
- [ ] **[RED]** Write test for rate limit enforcement: 11th request in 1 min returns 429
- [ ] **[GREEN]** Implement rate limiter

---

## Phase 9 — Frontend Auth Layer

- [ ] **[RED]** Write tests for `AuthProvider` context: unauthenticated state, loading state, authenticated state with user data
- [ ] **[GREEN]** Implement `frontend/src/app/providers/auth-provider.tsx` — calls `GET /api/v1/auth/me` on mount, manages auth state
- [ ] **[RED]** Write tests for `ProtectedRoute` wrapper: redirects to `/login` if unauthenticated, renders children if authenticated
- [ ] **[GREEN]** Implement `ProtectedRoute` or middleware in `frontend/src/middleware.ts` (Next.js route protection)
- [ ] **[GREEN]** Implement `/login` page at `frontend/src/app/login/page.tsx` — renders "Sign in with Google" button, links to `/api/v1/auth/google`
- [ ] **[GREEN]** Implement API client with automatic token refresh: intercept 401 responses, call `/api/v1/auth/refresh`, retry original request once. On second 401, redirect to `/login`
- [ ] **[RED]** Write tests for API client retry logic: 401 → refresh → retry → success, 401 → refresh fails → redirect
- [ ] **[GREEN]** Implement `frontend/src/lib/api-client.ts`
- [ ] Implement logout button component: calls `POST /api/v1/auth/logout`, clears auth state, redirects to `/login`

---

## Phase 10 — Session Cleanup (Background Job)

- [ ] Define Celery task `cleanup_expired_sessions` in `backend/infrastructure/jobs/session_cleanup.py`
- [ ] Schedule task to run daily via Celery Beat
- [ ] **[RED]** Write unit test for cleanup task: only deletes sessions where `expires_at < NOW()`
- [ ] **[GREEN]** Implement cleanup task

---

## Phase 11 — End-to-End Validation

- [ ] Full OAuth login flow works locally with real Google OAuth credentials
- [ ] First login creates workspace, user lands on `/workspace/<slug>/`
- [ ] Returning login resolves existing workspace
- [ ] Token refresh works transparently (force-expire access token, verify seamless continuation)
- [ ] Logout clears cookies, redirects to `/login`, subsequent requests return 401
- [ ] Audit log contains entries for all auth events
- [ ] Rate limiting blocks after 10 requests/min on auth endpoints

---

## Completion

**Status: COMPLETED** (fill date when done)

All checkboxes must be checked before marking COMPLETED. No exceptions.
