# EP-00 Bootstrap Specs — First-login Flow & Workspace Resolution

## Context

The workspace is the root container for all work in the system. Multi-tenant — multiple workspaces share the deployment and each user can belong to N of them. Every authenticated request must resolve an active workspace; unknown users without membership are blocked, not auto-provisioned.

> **Resolved 2026-04-14** (decisions_pending.md #14): No auto-create-personal-workspace. Workspace creation is a Superadmin-only action. First-login flow resolves against existing `workspace_memberships`.

---

## First Login Resolution Flow

WHEN a user completes Google OAuth and their `google_sub` resolves (either new or existing `users` row)
THEN the backend queries `workspace_memberships` for all rows with `user_id = users.id` AND `state = 'active'`

### Case: 0 active memberships

WHEN the user has zero active `workspace_memberships` rows
THEN the backend does NOT create any workspace or membership
AND the backend redirects to `/login?error=no_workspace` with a user-facing message: "Your account has no workspace assigned. Contact an administrator."
AND an audit event `login_blocked_no_workspace` is written
AND no JWT is issued, no session is created

### Case: exactly 1 active membership

WHEN the user has exactly one active `workspace_memberships` row
THEN the backend resolves that workspace as the active workspace
AND sets `active_workspace_id` on the session
AND redirects to `/workspace/<slug>/` (or `returnTo` deeplink if present)

### Case: N active memberships (N >= 2)

WHEN the user has multiple active `workspace_memberships` rows
THEN the backend looks up `session.last_chosen_workspace_id`
AND IF a last-chosen value is present AND still belongs to an active membership
THEN the backend routes to that workspace directly
AND IF no last-chosen value OR it is no longer valid
THEN the backend redirects to `/workspace/select` (workspace picker UI)

WHEN the user selects a workspace on `/workspace/select`
THEN the backend persists `last_chosen_workspace_id` on the session
AND redirects to `/workspace/<slug>/` (or `returnTo` if present)

---

## Workspace Creation (Superadmin only)

WHEN a superadmin calls `POST /api/v1/admin/workspaces` with `{ name, slug, initial_admin_user_id }`
THEN the backend creates the `workspaces` row (status=active, created_by=superadmin)
AND creates the initial `workspace_memberships` row for the given user with the `Workspace Admin` profile
AND writes an audit event `workspace_created` scoped to the new workspace
AND returns the created workspace

WHEN a non-superadmin attempts `POST /api/v1/admin/workspaces`
THEN the backend returns 403 `{ error: { code: "FORBIDDEN" } }`

---

## Deeplink Preservation (`returnTo`)

WHEN an unauthenticated request hits a protected path `/workspace/<slug>/...`
THEN the frontend captures the original path and redirects to `/login?returnTo=<encoded path>`

WHEN the user completes OAuth and is redirected to their active workspace
THEN if a valid `returnTo` param is present AND resolves to the same workspace-scoped path
THEN the backend redirects to `returnTo` instead of `/workspace/<slug>/`
AND IF `returnTo` is invalid (cross-workspace, non-whitelisted, or malformed) THEN it is ignored

---

## Bootstrap Race Condition Guard (User Upsert)

WHEN two concurrent OAuth callbacks arrive for the same `google_sub`
THEN the DB upsert (INSERT ... ON CONFLICT (google_sub) DO UPDATE) is atomic
AND exactly one `users` row exists after both requests complete

WHEN two concurrent workspace-creation requests use the same slug
THEN UNIQUE constraint on `workspaces.slug` forces one to fail with 409
AND the caller retries with a different slug (admin UI surfaces the collision)

---

## Superadmin Bootstrap

WHEN a user matching `SEED_SUPERADMIN_EMAILS` authenticates for the first time
THEN the resulting `users` row is created with `is_superadmin = true` AND `google_sub` pinned
AND an audit event `superadmin_seeded` is written with context `{ source: "env_seed" }`

WHEN an already-provisioned superadmin calls `POST /api/v1/admin/users/:id/grant-superadmin`
THEN the target user's `is_superadmin` flag is set to true
AND an audit event `superadmin_granted` is written with `actor_id` and `entity_id=target_user.id`

WHEN a non-superadmin attempts the same endpoint
THEN 403 is returned, no flag is changed

---

## Out of scope (for EP-00)

- Workspace invitation flows for non-superadmin admins (EP-10)
- Workspace switcher UX beyond the initial picker (EP-09 / EP-10 admin surface)
- Org auto-detection by email domain
- Workspace merge / split
