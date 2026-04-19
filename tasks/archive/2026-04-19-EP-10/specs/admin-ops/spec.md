# Spec: Audit Log, Health Dashboard & Support Tools
## US-107 — View Admin Audit Log
## US-108 — View Admin Health Dashboard
## US-109 — Operate Basic Support Tools

**Epic**: EP-10 — Configuration, Projects, Rules & Administration
**Priority**: US-107: Must | US-108: Should | US-109: Should
**Dependencies**: All other EP-10 stories (audit log is written by them), EP-08 (teams/notifications)

---

## Domain Model

### AuditEvent

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `workspace_id` | uuid | |
| `actor_id` | uuid or null | Null for system-generated events |
| `actor_display` | string | Denormalized name at time of event (preserved if member deleted) |
| `action` | string | e.g. `member_invited`, `rule_updated`, `jira_config_created` |
| `entity_type` | string | e.g. `workspace_member`, `validation_rule`, `jira_config` |
| `entity_id` | uuid | |
| `before_value` | jsonb or null | State before the change |
| `after_value` | jsonb or null | State after the change |
| `context` | jsonb or null | Additional metadata (project_id, rule_scope, etc.) |
| `created_at` | timestamp | Immutable — audit events are never updated or deleted |

Audit events are append-only. No UPDATE or DELETE is permitted on this table by application code.

---

## US-107: Admin Audit Log

### Query Audit Log

**WHEN** a member with `view_audit_log` capability submits `GET /api/v1/admin/audit-log`
**THEN** a paginated list of audit events is returned, ordered by `created_at` descending
**AND** default page size is 50 events; max is 200

**WHEN** query param `actor_id=uuid` is provided
**THEN** only events by that actor are returned

**WHEN** query param `action=member_suspended` is provided
**THEN** only events with that action are returned

**WHEN** query param `entity_type=validation_rule` is provided
**THEN** only events on that entity type are returned

**WHEN** query param `entity_id=uuid` is provided
**THEN** the full history of changes to that specific entity is returned, ordered oldest-first (useful for "who changed this rule and when")

**WHEN** query params `from=ISO8601&to=ISO8601` are provided
**THEN** events are filtered to that time window

**WHEN** multiple filters are combined (`actor_id + entity_type + from/to`)
**THEN** all filters are applied with AND logic

**WHEN** a member without `view_audit_log` capability makes the request
**THEN** `403 Forbidden` with `error.code: capability_required`

---

### Audit Event Immutability

**WHEN** any application code attempts to UPDATE or DELETE an audit event
**THEN** the operation is rejected at the database level (row-level security or constraint)
**AND** no API endpoint exists to modify or delete audit events

**WHEN** an audit log query returns an event for a member who has since been deleted
**THEN** the `actor_display` field still shows the denormalized name captured at event creation time
**AND** `actor_id` is preserved for cross-reference, even if the member record is gone

---

### Audit Action Reference

Audited actions (non-exhaustive; spec for writers: all admin mutations MUST emit an audit event):

| Action | Entity Type | Before/After |
|---|---|---|
| `member_invited` | `workspace_member` | after: `{email, state: invited}` |
| `member_activated` | `workspace_member` | before: `invited`, after: `active` |
| `member_suspended` | `workspace_member` | before: `active`, after: `suspended` |
| `member_deleted` | `workspace_member` | before state, after: `deleted` |
| `capabilities_changed` | `workspace_member` | before: `[caps]`, after: `[caps]` |
| `context_labels_changed` | `workspace_member` | before: `[labels]`, after: `[labels]` |
| `invite_resent` | `invitation` | context: `{invitation_id}` |
| `team_created` | `team` | after: `{name, member_ids}` |
| `team_updated` | `team` | before/after relevant fields |
| `team_deleted` | `team` | before: `{name, member_ids}` |
| `validation_rule_created` | `validation_rule` | after: full rule |
| `validation_rule_updated` | `validation_rule` | before/after changed fields |
| `validation_rule_deactivated` | `validation_rule` | before: `active: true`, after: `active: false` |
| `routing_rule_created` | `routing_rule` | after: full rule |
| `routing_rule_updated` | `routing_rule` | before/after |
| `project_created` | `project` | after: `{name, team_ids}` |
| `project_updated` | `project` | before/after |
| `project_archived` | `project` | before: `active`, after: `archived` |
| `context_source_added` | `context_source` | after: full source |
| `context_source_removed` | `context_source` | before: full source |
| `context_preset_created` | `context_preset` | after: `{name, source_count}` |
| `context_preset_updated` | `context_preset` | before/after |
| `jira_config_created` | `jira_config` | after: `{base_url, auth_type}` (no credentials) |
| `jira_credentials_updated` | `jira_config` | context: `{config_id}` (no credential values) |
| `jira_config_disabled` | `jira_config` | |
| `jira_config_enabled` | `jira_config` | |
| `jira_mapping_created` | `jira_project_mapping` | after: full mapping |
| `jira_export_retried` | `jira_sync_log` | context: `{work_item_id, attempt}` |
| `owner_reassigned` | `element` | before/after `owner_id` |
| `jira_health_degraded` | `jira_config` | context: `{error_type}` |

---

## US-108: Admin Health Dashboard

### Dashboard Data Structure

**WHEN** a member with `view_admin_dashboard` capability submits `GET /api/v1/admin/dashboard`
**THEN** the response returns all four health blocks in a single response

---

### Workspace Health Block

**WHEN** the workspace health block is requested
**THEN** it returns:
- `elements_by_state`: count per state (`draft`, `in_review`, `blocked`, `ready`, `archived`, `cancelled`)
- `critical_blocks`: count of elements with state `blocked` for more than 5 days
- `avg_time_to_ready_days`: rolling 30-day average (from `created_at` to `ready_at`) for elements that reached `ready`
- `stale_reviews`: count of review requests open for more than 7 days without activity

**WHEN** no elements exist yet
**THEN** all counts are `0` and averages are `null` — no error

---

### Organizational Health Block

**WHEN** the org health block is requested
**THEN** it returns:
- `active_members`: count of members with state `active`
- `teamless_members`: count of `active` members not belonging to any team
- `teams_without_lead`: count of teams with no `lead_member_id` set
- `teams_without_recent_activity`: count of teams where no member created or reviewed an element in the last 30 days
- `top_loaded_owners`: top 5 members by count of elements where `owner_id = member.id` and state is non-terminal, ordered descending

---

### Process Health Block

**WHEN** the process health block is requested
**THEN** it returns:
- `most_skipped_validations`: top 5 `(work_item_type, validation_type)` combinations where required validation was overridden, ordered by override count
- `override_rate_pct`: percentage of elements that reached `ready` via a forced override in the last 30 days
- `exported_vs_not_pct`: percentage of `ready` elements that have a linked Jira issue key vs those that do not
- `blocked_by_type`: count of `blocked` elements grouped by `work_item_type`
- `blocked_by_team`: count of `blocked` elements where `owner` belongs to each team

---

### Integration Health Block

**WHEN** the integration health block is requested
**THEN** it returns:
- `jira_state`: `ok` | `error` | `disabled` | `not_configured`
- `jira_last_check_at`: timestamp of last health check
- `jira_exports_last_24h`: `{success_count, failed_count, pending_count}`
- `jira_frequent_errors`: top 3 distinct `error_message` values from `jira_sync_log` in the last 7 days, with occurrence count
- `jira_last_sync_at`: timestamp of most recent successful export

**WHEN** Jira is not configured
**THEN** `jira_state: not_configured` and all other jira fields are `null`

---

### Dashboard Scoping

**WHEN** query param `project_id=uuid` is provided
**THEN** all metrics are scoped to elements belonging to that project
**AND** org health uses team/member associations of that project

**WHEN** a Project Admin (has `configure_project` but not `view_admin_dashboard`) calls the dashboard with `project_id`
**THEN** the request succeeds with project-scoped data
**AND** workspace-level metrics (total active members, etc.) are omitted or aggregated to project scope only

---

## US-109: Basic Support Tools

### Reassign Orphaned Element Owners

**WHEN** a member with `reassign_owner` capability submits `POST /api/v1/admin/support/reassign-owner` with `{work_item_id, new_owner_id}`
**THEN** the element's `owner_id` is updated to `new_owner_id`
**AND** the new owner must be an `active` member, otherwise rejected with `422` and `error.code: target_owner_inactive`
**AND** the previous owner (even if suspended/deleted) retains historical visibility of their work on the element
**AND** an SSE notification is dispatched to the new owner via EP-08 inbox
**AND** the audit log records `action: owner_reassigned`, `entity: element`, `before: {owner_id}`, `after: {owner_id}`, `actor`

**WHEN** `work_item_id` does not exist in the workspace
**THEN** rejected with `404 Not Found`

**WHEN** the element is in a terminal state (`ready`, `archived`, `cancelled`)
**THEN** rejected with `409 Conflict` and `error.code: element_in_terminal_state`

---

### Bulk Orphan Detection

**WHEN** `GET /api/v1/admin/support/orphaned-elements` is called by a member with `reassign_owner` capability
**THEN** the response returns elements where `owner_id` references a `suspended` or `deleted` member and element state is non-terminal
**AND** the response includes `{work_item_id, work_item_type, title, current_owner_id, current_owner_state, project_id}`
**AND** results are paginated; default 50 per page

---

### Reactivate Suspended Member

**WHEN** a member with `deactivate_members` capability submits `PATCH /api/v1/admin/members/{member_id}` with `{status: "active"}`
**AND** the current state is `suspended`
**THEN** the member is reactivated
**AND** any open orphan-owner alerts for this member are resolved (cleared from alert queue)
**AND** the audit log records `action: member_reactivated`

**WHEN** the current state is `deleted`
**THEN** rejected with `409 Conflict` and `error.code: deleted_member_cannot_reactivate`

---

### Resend Invitation (Support Context)

**WHEN** `GET /api/v1/admin/support/pending-invitations` is called by a member with `invite_members` capability
**THEN** all invitations with state `invited` and `expires_at < now() + 24h` (expiring soon or already expired) are returned
**AND** each entry includes `{invitation_id, email, invited_by, invited_at, expires_at, expired: bool}`

**WHEN** `POST /api/v1/admin/members/invitations/{id}/resend` is called for an expired invitation
**THEN** the invitation is renewed (new token, new expiry) and email re-dispatched
**AND** behavior is identical to the standard resend flow in US-105

---

### Retry Failed Jira Exports (Support Context)

**WHEN** `GET /api/v1/admin/support/failed-exports` is called by a member with `retry_exports` capability
**THEN** all `jira_sync_log` entries with `status: failed` are returned, ordered by `last_attempt_at` descending
**AND** each entry includes `{log_id, work_item_id, work_item_title, error_message, attempt_count, last_attempt_at}`

**WHEN** `POST /api/v1/admin/support/failed-exports/retry-all` is submitted
**THEN** all `status: failed` export log entries have new Celery tasks queued
**AND** status is updated to `retrying` for each
**AND** a bulk audit event is recorded: `action: jira_bulk_retry`, `count`, `actor`
**AND** this operation is rate-limited: rejected with `429` if called more than once per 10 minutes

---

### Detect Config-Blocked Elements

**WHEN** `GET /api/v1/admin/support/config-blocked-elements` is called
**THEN** the response returns elements where `state = blocked` and the block reason traces to a configuration issue:
  - Owner is `suspended` or `deleted`
  - Required validation rule references a deleted team (no eligible validators)
  - Element belongs to an archived project
**AND** each entry includes `{work_item_id, block_reason, detail}`

---

## Edge Cases

- Audit log query with very broad date range returns millions of rows: pagination enforced; max page size 200; no unbounded queries permitted.
- Health dashboard called on empty workspace: all counters return `0`, averages `null`, no error.
- Reassigning owner to a member in an archived project: allowed if the member is `active` in the workspace (project archival does not restrict member activity on existing elements).
- Support tool `retry-all` called while Jira is in `error` state: all tasks queue but immediately fail; the caller is warned via response field `{warning: "jira_config_in_error_state"}` (not a block — admin may be retrying after fixing credentials).

---

## API Endpoints Summary

| Method | Path | Required Capability |
|---|---|---|
| `GET` | `/api/v1/admin/audit-log` | `view_audit_log` |
| `GET` | `/api/v1/admin/dashboard` | `view_admin_dashboard` (or `configure_project` for scoped) |
| `GET` | `/api/v1/admin/support/orphaned-elements` | `reassign_owner` |
| `POST` | `/api/v1/admin/support/reassign-owner` | `reassign_owner` |
| `GET` | `/api/v1/admin/support/pending-invitations` | `invite_members` |
| `GET` | `/api/v1/admin/support/failed-exports` | `retry_exports` |
| `POST` | `/api/v1/admin/support/failed-exports/retry-all` | `retry_exports` |
| `GET` | `/api/v1/admin/support/config-blocked-elements` | `view_admin_dashboard` |
