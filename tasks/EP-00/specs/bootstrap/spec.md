# EP-00 Bootstrap Specs — Workspace Bootstrap

## Context

The workspace is the root container for all work in the system. Every user must belong to at least one workspace. Bootstrap ensures the first user to authenticate gets a functional workspace automatically, without requiring manual setup. Subsequent users may be invited (out of scope for EP-00) or self-provision (if allowed — out of scope for EP-00).

---

## First User: New System, No Workspace Exists

WHEN a user completes Google OAuth for the first time on a fresh system (no workspaces in DB)
THEN the backend creates a default workspace with:
  - `name`: derived from the user's email domain (e.g. `acme.com` → `Acme`) or `"My Workspace"` if domain is a public provider (gmail.com, outlook.com, etc.)
  - `slug`: URL-safe version of the name, uniqueness enforced
  - `created_by`: the authenticating user's ID
  - `status`: `active`
  - `created_at`, `updated_at`
AND the backend creates a `workspace_memberships` record:
  - `user_id`: the authenticating user
  - `workspace_id`: the new workspace
  - `role`: `admin`
  - `joined_at`: now
AND the user's JWT `workspace_id` claim is set to this new workspace
AND the user lands on `/workspace/<slug>/` after login
AND this bootstrap event is written to the audit log with `event_type: workspace_bootstrapped`

### Public Email Domain Detection

WHEN the user's email domain is in the public provider list (gmail.com, outlook.com, hotmail.com, yahoo.com, icloud.com)
THEN the workspace name defaults to `"My Workspace"`
AND the slug is generated as `my-workspace-<random 6 chars>` to avoid conflicts

---

## First User: System Has Existing Workspaces

WHEN a user authenticates and their `google_sub` exists in `users` but they have NO `workspace_memberships` rows
THEN the backend does NOT auto-create a workspace (they were previously unauthenticated without membership — edge case)
AND the user is redirected to `/onboarding` or `/login?error=no_workspace` (exact UX TBD, see open questions)
AND an audit entry is logged

WHEN a user authenticates and they have an existing `workspace_memberships` row
THEN the backend resolves the workspace normally (returning user flow below)

---

## Returning User: Existing Workspace Membership

WHEN a returning user completes Google OAuth
THEN the backend resolves the user record (US-002 upsert)
AND queries `workspace_memberships` for all active memberships of this user
AND selects the workspace with `is_default = true` for this user, OR the first membership by `joined_at` ASC if no default is set
AND sets `workspace_id` in the JWT claim
AND redirects to `/workspace/<slug>/`

WHEN a returning user has multiple workspace memberships
THEN the backend selects the default workspace (or first joined)
AND the user can switch workspaces after login (workspace switcher — separate epic, out of scope here)

---

## Bootstrap Race Condition Guard

WHEN two requests attempt to bootstrap the workspace for the same user simultaneously (e.g. double-click)
THEN the DB transaction uses `SELECT ... FOR UPDATE` or equivalent optimistic locking on the user row
AND exactly one workspace is created
AND both requests complete with a valid session pointing to the same workspace

WHEN two different users from the same organization log in at exactly the same time (concurrent first logins)
THEN each gets their own workspace (no automatic org detection at this stage — deferred)
AND workspace merging is not handled in EP-00

---

## Workspace Slug Uniqueness

WHEN a workspace is created and the derived slug already exists
THEN the backend appends a 4-digit random suffix (e.g. `acme-7f3a`)
AND retries up to 5 times before failing with 500 and alerting

---

## Open Questions (Requires Product Decision Before Implementation)

1. What happens when a new user authenticates on a system that has existing workspaces but they have no membership? Options:
   - A: Auto-create a new personal workspace (current default above for isolated MVP)
   - B: Show an invitation-required screen
   - C: Allow self-join if workspace is set to "open"
   Recommendation: A for MVP (no invite system yet), escalate if multi-tenant from day 1 is required.

2. Should workspace name default to email domain for corporate emails? Confirm the public provider blocklist is sufficient.

3. Is there a concept of "personal workspace" vs "team workspace" from day 1, or is every workspace the same type?
