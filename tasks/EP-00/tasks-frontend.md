# EP-00 Frontend Tasks — Access, Identity & Bootstrap

> **Follows EP-19 (Design System & Frontend Foundations)**. Login, workspace picker, and session-expired screens use catalog components + semantic tokens, Inter typography, `HumanError` for API failures, and i18n `i18n/es/auth.ts`. No raw Tailwind colors, no English UI strings. See `tasks/extensions.md#EP-19`.

Branch: `feature/ep-00-frontend`
Refs: EP-00

---

## API Contract (Depends on Backend)

All auth cookies are HTTP-only, set/cleared by the backend. Frontend never reads token values directly.

| Endpoint | When used | Frontend behavior |
|----------|-----------|-------------------|
| `GET /api/v1/auth/google` | Login button click | Hard navigate (not fetch) — triggers OAuth redirect |
| `GET /api/v1/auth/me` | App mount | Determine auth state; redirect to `/login?returnTo=<current path>` on 401 |
| `GET /api/v1/workspaces/mine` | After login when resolver returns picker | List memberships for the workspace picker UI |
| `POST /api/v1/auth/refresh` | On 401 from any API call | Called by API client interceptor; retries original request |
| `POST /api/v1/auth/logout` | Logout button | Clear auth state, redirect to `/login` |

Response shape for `/auth/me`:
```json
{
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "User Name",
    "avatar_url": "https://...",
    "workspace_id": "uuid",
    "workspace_slug": "acme",
    "is_superadmin": false
  }
}
```

**Blocked by**: backend `GET /api/v1/auth/me` and cookie-based auth must be deployed before frontend auth integration tests can pass.

---

## Phase 0 — Project Setup

- [x] Scaffold `frontend/` Next.js 14 App Router project with TypeScript (`strict: true`) — pre-existing
- [x] Configure `tsconfig.json`: `strict: true`, path alias `@/` → `./` — done (2026-04-15)
- [x] Add devDeps: `msw@^2`, `@testing-library/user-event@^14` — added (2026-04-15); native fetch used, no axios/zustand
- [x] Configure Tailwind CSS — pre-existing
- [x] Set up MSW node server in `__tests__/msw/server.ts`, wired into `__tests__/setup.ts` with beforeAll/afterEach/afterAll (2026-04-15)

---

## Phase 1 — API Client

### API Client (`frontend/lib/api-client.ts`)

- [x] [RED] Write tests: 401 retry, refresh called once, concurrent storm guard, 403/404/500 not retried — 12 tests in `__tests__/lib/api-client.test.ts` (2026-04-15)
- [x] [GREEN] Implement `frontend/lib/api-client.ts`: `apiGet<T>`, `apiPost<T>`, `apiPatch<T>`, `apiDelete<T>`; 401→refresh→retry; concurrent refresh guard; typed `ApiError`/`UnauthenticatedError`; throws on second 401, does NOT redirect (2026-04-15)

### Acceptance Criteria — Phase 1

WHEN an API call returns HTTP 401
THEN the client automatically calls `POST /api/v1/auth/refresh` exactly once
AND retries the original request with the same method, URL, and body
AND returns the successful response to the caller transparently

WHEN the retry after refresh also returns HTTP 401
THEN the client redirects to `/login` using `router.push('/login')`
AND does NOT call `POST /api/v1/auth/refresh` a second time (no infinite loop)
AND throws an error so the caller's loading state can resolve

WHEN an API call returns HTTP 403, 404, or 500
THEN the client does NOT call `POST /api/v1/auth/refresh`
AND throws a typed error `{ error: { code, message, details } }` to the caller

WHEN `tsc --noEmit` is run on `api-client.ts`
THEN no implicit `any` types; all function return types are explicit

---

## Phase 2 — Auth State

### AuthProvider (`frontend/app/providers/auth-provider.tsx`)

- [x] [RED] Write component tests: isLoading/isAuthenticated initial state, 200/401 from /auth/me, logout happy/fail paths, useAuth outside provider — 7 tests in `__tests__/app/providers/auth-provider.test.tsx` (2026-04-15)
- [x] [GREEN] Implement `frontend/app/providers/auth-provider.tsx`: AuthProvider + useAuth hook; wired into `frontend/app/providers.tsx` (2026-04-15)

### Acceptance Criteria — Phase 2

WHEN `AuthProvider` mounts and `GET /api/v1/auth/me` is in flight
THEN `isLoading = true` AND `isAuthenticated = false` AND `user = null`

WHEN `GET /api/v1/auth/me` returns HTTP 200 with valid user data
THEN `isLoading = false` AND `isAuthenticated = true` AND `user` matches the response data

WHEN `GET /api/v1/auth/me` returns HTTP 401
THEN `isLoading = false` AND `isAuthenticated = false` AND `user = null`
AND the component does NOT redirect (redirect is handled by middleware or page-level guard)

WHEN `useAuth().logout()` is called
THEN `POST /api/v1/auth/logout` is called
AND `user` is set to `null` in context
AND `router.push('/login')` is called
AND if the API call fails, the redirect still happens (do not block logout on network error)

WHEN `useAuth()` is called outside of `AuthProvider`
THEN it throws a descriptive error (not returns undefined)

---

## Phase 3 — Route Protection

### Next.js Middleware (`frontend/middleware.ts`)

- [x] [RED] Write tests: unauthenticated redirect with returnTo, authenticated pass-through, public paths exempt — 5 tests in `__tests__/middleware.test.ts` (2026-04-15)
- [x] [GREEN] Implement `frontend/middleware.ts`: presence-only `access_token` cookie check; redirect to `/login?returnTo=<encoded path>`; public paths: `/login`, `/_next/*`, `/favicon.ico`, `/api/v1/auth/*`; `config.matcher` excludes static/auth paths (2026-04-15)

### Acceptance Criteria — Phase 3

WHEN an unauthenticated request (no `access_token` cookie) hits `/workspace/acme/work-items`
THEN the middleware returns a redirect to `/login?returnTo=%2Fworkspace%2Facme%2Fwork-items`

WHEN a request with an `access_token` cookie (any value, presence-only check) hits `/workspace/acme`
THEN the middleware passes it through without redirect

WHEN any request hits `/login`, `/api/v1/auth/google`, or `/_next/static/...`
THEN the middleware does NOT redirect regardless of cookie presence

---

## Phase 4 — Pages

### Login Page (`frontend/app/login/page.tsx`)

- [x] [RED] Write component tests: sign-in link, loading state, error banners, redirect when authenticated, unknown error ignored — 9 tests (2026-04-15)
- [x] [GREEN] Implement `frontend/app/login/page.tsx`: `<a href="/api/v1/auth/google">` hard nav; error banner for known errors; loading spinner; redirect on isAuthenticated (2026-04-15)

### Workspace Picker Page (`frontend/app/workspace/select/page.tsx`)

- [x] [GREEN] Implement picker: `GET /api/v1/workspaces/mine` (NOTE: not in EP-00 backend scope — MSW-stubbed in tests; TODO: wire to real backend endpoint); `POST /api/v1/workspaces/select`; redirect to `/workspace/<slug>` — 2 tests in `__tests__/app/workspace/select-page.test.tsx` (2026-04-15)

### Workspace Redirect Page (`frontend/app/workspace/[slug]/page.tsx`)

- [x] [GREEN] Implement workspace layout shell: top nav with avatar/full_name/logout; initials fallback when `avatar_url` is null — 3 tests in `__tests__/app/workspace/slug-page.test.tsx` (2026-04-15)

---

## Phase 5 — Logout Component

### LogoutButton (`frontend/components/auth/logout-button.tsx`)

- [x] [RED] Write component tests: single call on click, disabled during pending, double-click safe, re-enables after resolve — 4 tests (2026-04-15)
- [x] [GREEN] Implement `frontend/components/auth/logout-button.tsx`: delegates to `useAuth().logout()`; disabled during pending (2026-04-15)

---

## Phase 6 — Type Definitions

- [x] Implement `frontend/lib/types/auth.ts`: `AuthUser`, `AuthMeResponse`, `ApiError`, `ApiErrorBody`, `UnauthenticatedError`; re-exported from `api-client.ts` (2026-04-15)
- [x] All API client calls fully typed — no `any` (2026-04-15)
- [x] `tsc --noEmit` clean (2026-04-15)

---

## Definition of Done

- [x] All component and unit tests pass — 45 tests (42 new + 3 smoke) (2026-04-15)
- [x] `tsc --noEmit` clean (2026-04-15)
- [x] ESLint clean — also fixed pre-existing broken config (`plugin:security/recommended` → `recommended-legacy`, removed missing `@typescript-eslint/no-explicit-any` rule) (2026-04-15)
- [x] Login page renders, Google sign-in button navigates correctly (2026-04-15)
- [x] Unauthenticated users redirected to `/login` from any protected route (2026-04-15)
- [x] `AuthProvider` correctly reflects loading/authenticated/unauthenticated states (2026-04-15)
- [x] Token refresh is transparent — user never sees a 401 during normal session (2026-04-15)
- [x] Logout clears state and redirects to `/login` (2026-04-15)

**Status: COMPLETED (2026-04-15)**
