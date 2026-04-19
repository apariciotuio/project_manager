# Spec: Member Management & Operational Capabilities
## US-105 — Manage Workspace Members
## US-106 — Manage Operational Capabilities and Admin Scope

**Epic**: EP-10 — Configuration, Projects, Rules & Administration
**Priority**: Must
**Dependencies**: EP-00 (auth, google_sub identity), EP-08 (teams)

---

## Domain Model

### Member States

| State | Description |
|---|---|
| `invited` | Invitation sent, user has not yet signed in |
| `active` | Can operate normally |
| `suspended` | Cannot operate; history preserved; owned items trigger alert |
| `deleted` | Logically removed; audit trail and historical participation preserved |

### Operational Capabilities (NOT roles — additive per member)

| Capability | Description |
|---|---|
| `invite_members` | Can send workspace invitations |
| `deactivate_members` | Can suspend or logically delete members |
| `manage_teams` | Can create, edit, delete teams and manage their membership |
| `configure_workspace_rules` | Can define workspace-level validation and routing rules |
| `configure_project` | Can configure context sources, templates, and rules for a project |
| `configure_integration` | Can configure Jira credentials and mappings |
| `view_audit_log` | Can query the admin audit log |
| `view_admin_dashboard` | Can access workspace health dashboard |
| `reassign_owner` | Can reassign owner of any element (not limited to own items) |
| `retry_exports` | Can trigger manual Jira export retry |

### Context Labels (separate from capabilities)

Functional profiles: `product`, `tech`, `business`, `qa`. Used for routing suggestions and validator hints. Never imply operational permissions.

---

## US-105: Manage Workspace Members

### Invite Flow

**WHEN** a member with `invite_members` capability submits `POST /api/v1/admin/members/invite` with `{email, context_labels[], team_ids[]}` for an email not already in the workspace
**THEN** a workspace invitation record is created with state `invited`
**AND** a unique invite token (TTL 7 days) is generated and stored hashed
**AND** an invitation email is dispatched via background task (Celery)
**AND** the audit log records `actor`, `action: member_invited`, `entity: invitation`, `email`, `timestamp`
**AND** the response returns `{invitation_id, email, status: "invited", expires_at}`

**WHEN** the same endpoint is called for an email that already has an `active` member record
**THEN** the request is rejected with `409 Conflict` and `error.code: member_already_active`

**WHEN** the same endpoint is called for an email that has an `invited` state
**THEN** the request is rejected with `409 Conflict` and `error.code: invite_pending`
**AND** the response includes `{invitation_id, resend_url}` so the caller knows to use the resend endpoint

**WHEN** a caller without `invite_members` capability makes the request
**THEN** the response is `403 Forbidden` with `error.code: capability_required`

---

### Invitation Acceptance (First Login via EP-00 OAuth)

**WHEN** a user signs in via Google OAuth and their `google_sub` maps to no existing user
**AND** a pending invitation exists for their verified Google email
**THEN** a `workspace_memberships` record is created with state `active`
**AND** the invitation token is consumed (marked used, not deleted)
**AND** context labels and initial team memberships from the invitation are applied
**AND** the audit log records `action: member_activated`, `entity: workspace_memberships`, `via: invite_acceptance`

**WHEN** a user signs in and their email has no pending invitation and workspace is not open-join
**THEN** access is denied with an informative error (not a generic 403)

---

### Resend Invitation

**WHEN** a member with `invite_members` capability submits `POST /api/v1/admin/members/invitations/{id}/resend`
**THEN** a new invite token is generated (old token invalidated)
**AND** the expiry resets to 7 days from now
**AND** the invitation email is re-dispatched
**AND** the audit log records `action: invite_resent`

**WHEN** the invitation state is not `invited` (already accepted or cancelled)
**THEN** the request is rejected with `409 Conflict` and `error.code: invite_not_resendable`

---

### Suspension

**WHEN** a member with `deactivate_members` capability submits `PATCH /api/v1/admin/members/{member_id}` with `{status: "suspended"}`
**THEN** the member state transitions to `suspended`
**AND** the system queries for elements where `owner_id = member_id` and state is not terminal (`ready`, `archived`, `cancelled`)
**AND** if any open-owned elements exist, an admin alert is queued: `{type: orphan_owner_alert, member_id, open_element_ids[], count}`
**AND** the SSE notification (EP-08 fan-out) is dispatched to all members with `view_admin_dashboard` capability
**AND** the member is removed from future assignment suggestions
**AND** the audit log records `action: member_suspended`, `before: active`, `after: suspended`

**WHEN** the member being suspended is the last `Workspace Admin` (holds all admin capabilities)
**THEN** the request is rejected with `409 Conflict` and `error.code: cannot_suspend_last_admin`

**WHEN** a suspended member attempts any write or state-change operation
**THEN** every request returns `403 Forbidden` with `error.code: member_suspended`

---

### Logical Delete

**WHEN** a member with `deactivate_members` capability submits `PATCH /api/v1/admin/members/{member_id}` with `{status: "deleted"}`
**THEN** the member state transitions to `deleted`
**AND** the same orphan-owner alert flow as suspension is triggered
**AND** the member's historical audit entries, review participations, and comments are preserved (user identity anonymized display is optional, not deletion)
**AND** all active sessions for that member are invalidated (JWT blocklist or short-expiry enforcement)
**AND** the member no longer appears in assignee/reviewer suggestion lists
**AND** the audit log records `action: member_deleted`, `before_state`, `after_state: deleted`

**WHEN** attempting to logically delete the last admin
**THEN** rejected with `409 Conflict` and `error.code: cannot_delete_last_admin`

---

### Member Listing and Filtering

**WHEN** a member with `view_admin_dashboard` capability calls `GET /api/v1/admin/members`
**THEN** the response returns paginated members with `{id, name, email, state, context_labels[], capabilities[], teams[], created_at, last_active_at}`

**WHEN** query param `state=invited` is provided
**THEN** only members in `invited` state are returned

**WHEN** query param `teamless=true` is provided
**THEN** only members not belonging to any team are returned (used for health dashboard routing gap detection)

---

## US-106: Manage Operational Capabilities and Admin Scope

### Capability Assignment

**WHEN** a member with `deactivate_members` AND `configure_workspace_rules` capabilities submits `PATCH /api/v1/admin/members/{member_id}/capabilities` with `{grant: ["capability_name"], revoke: []}`
**THEN** the listed capabilities are added to the member's capability set
**AND** the audit log records `action: capabilities_changed`, `before: old_set`, `after: new_set`, `actor`

**WHEN** the `grant` list contains an unrecognized capability name
**THEN** the request is rejected with `422 Unprocessable Entity` and `error.code: unknown_capability`

**WHEN** a caller attempts to grant capabilities they themselves do not hold
**THEN** the request is rejected with `403 Forbidden` and `error.code: cannot_grant_unpossessed_capability`

---

### Context Label Assignment

**WHEN** any member with `invite_members` capability submits `PATCH /api/v1/admin/members/{member_id}/context-labels` with `{labels: ["product", "tech"]}`
**THEN** the context labels are updated on the member record
**AND** the routing engine immediately uses the new labels for future suggestions
**AND** the audit log records `action: context_labels_changed`

**WHEN** a label outside the allowed set (`product`, `tech`, `business`, `qa`) is submitted
**THEN** the request is rejected with `422 Unprocessable Entity`

---

### Capability Enforcement Middleware

**WHEN** any admin endpoint is called
**THEN** the middleware checks the `required_capabilities` annotation of the endpoint against the calling member's capability set
**AND** if ANY required capability is missing, the request is rejected with `403 Forbidden` BEFORE reaching the handler
**AND** no partial execution occurs on capability failure

**WHEN** the JWT is valid but the workspace_memberships record is `suspended` or `deleted`
**THEN** all requests return `403 Forbidden` with `error.code: member_inactive` regardless of capabilities

---

## Edge Cases

- Member suspended while holding open reviews: existing review responses are preserved; no new reviews can be assigned.
- Member deleted while being team lead: team lead field is cleared; SSE alert sent to workspace admins.
- Two admins simultaneously modify the same member's capabilities: last-write-wins at DB level with optimistic locking (version field); audit log records both changes.
- Member has multiple context labels AND multiple team memberships: both are preserved independently; routing hints use intersection logic.
- Workspace has no configured teams: member management still works; routing suggestions fall back to context labels only.

---

## API Endpoints Summary

| Method | Path | Required Capability |
|---|---|---|
| `POST` | `/api/v1/admin/members/invite` | `invite_members` |
| `GET` | `/api/v1/admin/members` | `view_admin_dashboard` |
| `GET` | `/api/v1/admin/members/{id}` | `view_admin_dashboard` |
| `PATCH` | `/api/v1/admin/members/{id}` | `deactivate_members` |
| `PATCH` | `/api/v1/admin/members/{id}/capabilities` | `deactivate_members` + `configure_workspace_rules` |
| `PATCH` | `/api/v1/admin/members/{id}/context-labels` | `invite_members` |
| `GET` | `/api/v1/admin/members/invitations` | `view_admin_dashboard` |
| `POST` | `/api/v1/admin/members/invitations/{id}/resend` | `invite_members` |
