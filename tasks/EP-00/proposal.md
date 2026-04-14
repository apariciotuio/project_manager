# EP-00 — Access, Identity & Bootstrap

## Business Need

The system requires secure authentication and identity resolution before any functionality is accessible. Users must log in via Google OAuth, have a persistent profile, and be routed to their workspace. This is the foundation — nothing works without it.

## Objectives

- Authenticate users via Google OAuth (no other providers)
- Create/resolve unique user profiles (name, email, avatar) keyed by `google_sub`
- Protect all routes behind auth middleware
- Resolve active workspace membership after login (0 → block; 1 → land; N → picker)
- Support multi-workspace routing (slug/subdomain) with PostgreSQL RLS isolation
- Seed platform superadmins from config (`SEED_SUPERADMIN_EMAILS`); no CLI

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-001 | Sign in with Google OAuth | Must |
| US-002 | Create or resolve unique user profile | Must |
| US-003 | Manage session and protected route access | Must |

## Acceptance Criteria

- WHEN a user visits the app unauthenticated THEN they are redirected to `/login` with `returnTo` preserved
- WHEN OAuth succeeds THEN a user profile is created (first time) or resolved (returning) by `google_sub`
- WHEN authenticated AND user has 0 active memberships THEN login is blocked with "contact admin"
- WHEN authenticated AND user has 1 active membership THEN the user lands directly in that workspace
- WHEN authenticated AND user has N active memberships THEN a workspace picker is shown (last-chosen persisted)
- WHEN session expires THEN the user is redirected to login gracefully with `returnTo`
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
