# EP-00 Frontend Tasks — Access, Identity & Bootstrap

Branch: `feature/ep-00-frontend`
Refs: EP-00

---

## API Contract (Depends on Backend)

All auth cookies are HTTP-only, set/cleared by the backend. Frontend never reads token values directly.

| Endpoint | When used | Frontend behavior |
|----------|-----------|-------------------|
| `GET /api/v1/auth/google` | Login button click | Hard navigate (not fetch) — triggers OAuth redirect |
| `GET /api/v1/auth/me` | App mount | Determine auth state; redirect to `/login` on 401 |
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
    "workspace_slug": "acme"
  }
}
```

**Blocked by**: backend `GET /api/v1/auth/me` and cookie-based auth must be deployed before frontend auth integration tests can pass.

---

## Phase 0 — Project Setup

- [ ] Scaffold `frontend/` Next.js 14 App Router project with TypeScript (`strict: true`)
- [ ] Configure `tsconfig.json`: `strict: true`, `noImplicitAny: true`, path alias `@/` → `src/`
- [ ] Add dependencies: `axios` (or `ky`), `zustand` (or `jotai`), `@testing-library/react`, `@testing-library/user-event`, `vitest` (or `jest` with jsdom), `msw` for API mocking
- [ ] Configure Tailwind CSS with project design tokens (colors, spacing, font)
- [ ] Set up MSW handler stubs for `/api/v1/auth/*` endpoints for test environment

---

## Phase 1 — API Client

### API Client (`src/lib/api-client.ts`)

- [ ] [RED] Write tests for API client retry logic: 401 on original request → calls `POST /api/v1/auth/refresh` → retries original request → returns success; second consecutive 401 after refresh → redirects to `/login` without infinite loop
- [ ] [RED] Write test: non-401 errors (403, 404, 500) are not retried
- [ ] [GREEN] Implement `src/lib/api-client.ts`:
  - Axios (or ky) instance with `baseURL`, `withCredentials: true`
  - Response interceptor: on 401, call `/auth/refresh` once, retry; on second 401, `router.push('/login')`
  - All responses typed; error responses narrowed to `{ error: { code, message, details } }`
- [ ] Export typed helper functions: `get<T>`, `post<T>`, `patch<T>`, `del<T>`

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

### AuthProvider (`src/app/providers/auth-provider.tsx`)

Props interface:
```typescript
interface AuthState {
  user: AuthUser | null
  isLoading: boolean
  isAuthenticated: boolean
  logout: () => Promise<void>
}

interface AuthUser {
  id: string
  email: string
  full_name: string
  avatar_url: string | null
  workspace_id: string
  workspace_slug: string
}
```

- [ ] [RED] Write component tests for `AuthProvider`:
  - Initial render: `isLoading = true`, `isAuthenticated = false`
  - After successful `GET /auth/me`: `isAuthenticated = true`, user populated
  - After 401 from `GET /auth/me`: `isAuthenticated = false`, user is null
- [ ] [GREEN] Implement `src/app/providers/auth-provider.tsx`:
  - Calls `GET /api/v1/auth/me` on mount
  - Exposes `AuthContext` with `user`, `isLoading`, `isAuthenticated`, `logout()`
  - `logout()` calls `POST /api/v1/auth/logout`, clears user state, redirects to `/login`
- [ ] Implement `useAuth()` hook: `export function useAuth(): AuthState` — throws if used outside `AuthProvider`

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

### Next.js Middleware (`src/middleware.ts`)

- [ ] [RED] Write tests for middleware redirect logic: unauthenticated request to `/workspace/*` redirects to `/login`, authenticated request passes through, `/login` is always accessible without auth
- [ ] [GREEN] Implement `src/middleware.ts`:
  - Check for `access_token` cookie presence (existence check only — never read value in JS)
  - Redirect unauthenticated requests to protected paths → `/login`
  - Public paths: `/login`, `/api/v1/auth/*`, `/_next/*`, `/favicon.ico`
- [ ] Configure `config.matcher` to exclude static assets and API routes

### Acceptance Criteria — Phase 3

WHEN an unauthenticated request (no `access_token` cookie) hits `/workspace/acme/work-items`
THEN the middleware returns a redirect to `/login`
AND the original path is NOT preserved as a `returnTo` param (not required in MVP)

WHEN a request with an `access_token` cookie (any value, presence-only check) hits `/workspace/acme`
THEN the middleware passes it through without redirect
(note: middleware does NOT validate JWT; that happens in the backend)

WHEN any request hits `/login`, `/api/v1/auth/google`, or `/_next/static/...`
THEN the middleware does NOT redirect regardless of cookie presence

WHEN `config.matcher` is evaluated
THEN it does NOT match `/_next/*`, `/favicon.ico`, or any path under `/api/v1/auth/`

---

## Phase 4 — Pages

### Login Page (`src/app/login/page.tsx`)

Component interface:
```typescript
// No props — standalone page
// Reads `?error=` query param from failed OAuth callback
```

- [ ] [GREEN] Implement `src/app/login/page.tsx`:
  - "Sign in with Google" button: `<a href="/api/v1/auth/google">` (hard navigation, not `router.push`)
  - Error banner if `?error=oauth_failed` or `?error=session_expired` query param present
  - Loading spinner while `AuthProvider` is resolving (hide login UI during check)
  - Redirect to `/workspace/{slug}` if already authenticated
- [ ] [RED] Write component test: renders Google sign-in button, shows error banner when `?error` param present, does not render button when authenticated

### Acceptance Criteria — Login Page

WHEN the login page renders and `AuthProvider` is in `isLoading = true` state
THEN a loading spinner is shown and the Google sign-in button is NOT rendered

WHEN the login page renders and `isAuthenticated = false` and `isLoading = false`
THEN the Google sign-in button is rendered as an `<a>` tag pointing to `/api/v1/auth/google`
AND the button is NOT a `<button>` that calls `router.push` (hard navigation required for OAuth redirect)

WHEN the login page renders with `?error=oauth_failed` in the query string
THEN an error banner is visible with a human-readable message
AND the sign-in button is still present

WHEN the login page renders and `isAuthenticated = true`
THEN `router.replace('/workspace/{workspace_slug}')` is called
AND the login UI is NOT rendered (no flash)

WHEN the `?error` param is not one of the recognized values (`oauth_failed`, `session_expired`, `invalid_state`, `cancelled`)
THEN no error banner is shown (ignore unknown error params)

### Workspace Redirect Page (`src/app/workspace/[slug]/page.tsx`)

- [ ] [GREEN] Implement workspace root page as a layout shell: renders children, shows user avatar + logout in top nav
- [ ] Use `useAuth()` to display `user.full_name` and `user.avatar_url` in nav
- [ ] Fallback avatar: user initials when `avatar_url` is null

### Acceptance Criteria — Workspace Layout

WHEN the workspace layout renders with a user whose `avatar_url` is a valid URL
THEN the nav shows the avatar image with `alt` text set to `user.full_name`

WHEN the workspace layout renders with a user whose `avatar_url` is `null`
THEN the nav shows a circle with the user's initials (first char of first name + first char of last name from `full_name`)
AND no broken `<img>` tag is rendered

---

## Phase 5 — Logout Component

### LogoutButton (`src/components/auth/logout-button.tsx`)

Props interface:
```typescript
interface LogoutButtonProps {
  className?: string
}
```

- [ ] [RED] Write component test: button click calls `logout()` from `useAuth()`, shows loading state during logout, does not throw on double-click
- [ ] [GREEN] Implement `src/components/auth/logout-button.tsx`:
  - Calls `logout()` from `AuthProvider` context
  - Disabled during logout in progress
  - No direct API calls — delegates entirely to `useAuth().logout()`

### Acceptance Criteria — Phase 5

WHEN the LogoutButton is clicked
THEN it calls `useAuth().logout()` exactly once
AND becomes disabled (no further clicks processed) while the logout promise is pending

WHEN the button is clicked a second time while the first click is still processing (double-click)
THEN `logout()` is NOT called a second time
AND no exception is thrown

WHEN `logout()` resolves (success or failure)
THEN the button returns to its enabled state (or the page redirects — whichever comes first)

---

## Phase 6 — Type Definitions

- [ ] Implement `src/types/auth.ts` — TypeScript interfaces for all auth-related API responses: `AuthUser`, `AuthMeResponse`, `ApiError`
- [ ] Ensure all API client calls are fully typed (no `any`)
- [ ] Run `tsc --noEmit` and fix all errors

---

## Definition of Done

- [ ] All component and unit tests pass
- [ ] `tsc --noEmit` clean
- [ ] ESLint clean
- [ ] Login page renders, Google sign-in button navigates correctly
- [ ] Unauthenticated users redirected to `/login` from any protected route
- [ ] `AuthProvider` correctly reflects loading/authenticated/unauthenticated states
- [ ] Token refresh is transparent — user never sees a 401 during normal session
- [ ] Logout clears state and redirects to `/login`
