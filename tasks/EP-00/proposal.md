# EP-00 — Access, Identity & Bootstrap

## Business Need

The system requires secure authentication and identity resolution before any functionality is accessible. Users must log in via Google OAuth, have a persistent profile, and be routed to their workspace. This is the foundation — nothing works without it.

## Objectives

- Authenticate users via Google OAuth
- Create/resolve unique user profiles (name, email, avatar)
- Protect all routes behind auth middleware
- Resolve workspace membership after login
- Bootstrap initial workspace if none exists

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-001 | Sign in with Google OAuth | Must |
| US-002 | Create or resolve unique user profile | Must |
| US-003 | Manage session and protected route access | Must |

## Acceptance Criteria

- WHEN a user visits the app unauthenticated THEN they are redirected to Google OAuth
- WHEN OAuth succeeds THEN a user profile is created (first time) or resolved (returning)
- WHEN authenticated THEN the user lands in their workspace
- WHEN session expires THEN the user is redirected to login gracefully
- WHEN accessing a protected route without session THEN 401/redirect
- AND login/logout events are auditable

## Technical Notes

- Auth middleware for all protected routes
- Session management (JWT or server-side sessions)
- Workspace bootstrap on first login (create default workspace if none)
- Structured logging for auth events and errors

## Dependencies

None — this is the foundation.

## Complexity Assessment

**Medium** — OAuth integration is well-understood but session management, workspace bootstrap, and security hardening need careful design.

## Risks

- Google OAuth token refresh edge cases
- Session expiration UX (mid-work loss)
- First-user bootstrap race conditions
