# Spec: Jira Integration Configuration
## US-104 — Configure Jira Integration

**Epic**: EP-10 — Configuration, Projects, Rules & Administration
**Priority**: Must
**Dependencies**: EP-00 (workspace identity), US-100/US-101 (project context)

---

## Domain Model

### JiraConfig

One config per workspace (or per project if project-specific Jira is needed).

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `workspace_id` | uuid | |
| `project_id` | uuid or null | Null = workspace-level; set = project-specific override |
| `base_url` | string | Jira instance URL (e.g. `https://acme.atlassian.net`) |
| `auth_type` | enum | `api_token`, `oauth2` |
| `credentials_ref` | string | Reference to encrypted secrets store key (never stored plaintext) |
| `default_jira_project_key` | string or null | Default Jira project for element exports |
| `state` | enum | `active`, `disabled`, `error` |
| `last_health_check_at` | timestamp or null | |
| `last_health_check_status` | enum or null | `ok`, `auth_failure`, `unreachable`, `config_error` |
| `last_sync_at` | timestamp or null | |
| `created_by` | uuid | |
| `updated_at` | timestamp | |

### JiraProjectMapping

Maps workspace projects to Jira project keys, with field mappings.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `jira_config_id` | uuid | |
| `workspace_project_id` | uuid | |
| `jira_project_key` | string | e.g. `ACME` |
| `work_item_type_mappings` | json | `{feature: "Story", bug: "Bug", spike: "Task", ...}` |
| `active` | bool | |

### JiraSyncLog

One record per export attempt.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `jira_config_id` | uuid | |
| `work_item_id` | uuid | |
| `jira_issue_key` | string or null | Populated on success |
| `status` | enum | `pending`, `success`, `failed`, `retrying` |
| `error_message` | string or null | |
| `attempt_count` | int | |
| `last_attempt_at` | timestamp | |
| `triggered_by` | uuid or null | null = automatic, set = manual retry actor |

---

## US-104: Configure Jira Integration

### Create Jira Configuration

**WHEN** a member with `configure_integration` capability submits `POST /api/v1/admin/integrations/jira` with `{base_url, auth_type, credentials: {api_token or oauth2_token}, default_jira_project_key}`
**THEN** credentials are encrypted and stored via secrets store; only a reference key is persisted in `jira_config`
**AND** the plaintext credentials are NOT logged, NOT stored in the audit log (audit records `action: jira_config_created`, `config_id` only)
**AND** an async health check probe is queued immediately (Celery task)
**AND** the response returns `{config_id, state: "active", health_check: "pending"}`

**WHEN** a Jira config already exists for the same `(workspace_id, project_id=null)` scope
**THEN** rejected with `409 Conflict` and `error.code: jira_config_exists`
**AND** the caller is advised to update the existing config

**WHEN** `base_url` is not a valid HTTPS URL
**THEN** rejected with `422` and `error.code: invalid_base_url`

**WHEN** `auth_type = api_token` and no `api_token` is provided
**THEN** rejected with `422` and `error.code: credentials_missing`

---

### Update Jira Credentials

**WHEN** a member with `configure_integration` capability submits `PATCH /api/v1/admin/integrations/jira/{config_id}` with `{credentials: {...}}`
**THEN** the new credentials are encrypted and stored, replacing the old reference
**AND** the old credentials reference is purged from the secrets store
**AND** an async health check probe is re-queued
**AND** the audit log records `action: jira_credentials_updated`, `config_id` (no credential values)

**WHEN** only non-credential fields are updated (e.g. `default_jira_project_key`, `state`)
**THEN** no re-encryption occurs; credentials reference is unchanged
**AND** the audit log records `action: jira_config_updated`, `before: {changed_fields}`, `after: {changed_fields}`

---

### Connection Test (Synchronous)

**WHEN** a member with `configure_integration` capability submits `POST /api/v1/admin/integrations/jira/{config_id}/test`
**THEN** a synchronous HTTP probe is executed against the Jira API (max 10 second timeout)
**AND** the probe attempts: GET `/rest/api/3/myself` to validate auth
**AND** if successful, the response is `{status: "ok", jira_user: {account_id, display_name}, latency_ms}`
**AND** if auth fails, the response is `{status: "auth_failure", error: "Invalid API token or insufficient permissions"}`
**AND** if the host is unreachable, the response is `{status: "unreachable", error: "Connection timed out"}`
**AND** `jira_config.last_health_check_at` and `last_health_check_status` are updated
**AND** the response is always `200 OK` (connection test is a probe — the HTTP status reflects API success, not connection status)

**WHEN** the config is in `disabled` state
**THEN** rejected with `409 Conflict` and `error.code: config_disabled`

---

### Health Check (Async, Background)

**WHEN** the Celery health check task executes for a Jira config
**THEN** it performs the same `/rest/api/3/myself` probe
**AND** on success: `state` remains `active`, `last_health_check_status: ok`
**AND** on failure: `last_health_check_status` is updated to the error type; `state` transitions to `error` if 3 consecutive failures
**AND** on state transition to `error`: an SSE notification is dispatched to all members with `configure_integration` or `view_admin_dashboard` capability
**AND** a `jira_health_degraded` audit log entry is created

**WHEN** a health check re-enters `ok` after an `error` state
**THEN** `state` transitions back to `active`
**AND** the audit log records `action: jira_config_recovered`

---

### Project Mappings

**WHEN** a member with `configure_integration` capability submits `POST /api/v1/admin/integrations/jira/{config_id}/mappings` with `{workspace_project_id, jira_project_key, work_item_type_mappings}`
**THEN** a project mapping is created
**AND** the `jira_project_key` is validated against the configured Jira instance via a lightweight probe (GET `/rest/api/3/project/{key}`) before saving
**AND** if the key does not exist in Jira, rejected with `422` and `error.code: jira_project_not_found`
**AND** the audit log records `action: jira_mapping_created`

**WHEN** `work_item_type_mappings` is not provided
**THEN** a sensible default is applied: `{feature: "Story", bug: "Bug", spike: "Task", initiative: "Epic", task: "Task"}`

**WHEN** `GET /api/v1/admin/integrations/jira/{config_id}/mappings` is called
**THEN** all mappings for the config are returned with their active state and element type mappings

---

### Disable / Re-enable Integration

**WHEN** a member with `configure_integration` capability submits `PATCH /api/v1/admin/integrations/jira/{config_id}` with `{state: "disabled"}`
**THEN** the config state transitions to `disabled`
**AND** no new export tasks are queued for elements in the workspace
**AND** pending export tasks already in queue are allowed to complete (not cancelled)
**AND** the audit log records `action: jira_config_disabled`

**WHEN** `{state: "active"}` is submitted
**THEN** the config is re-enabled and a health check probe is queued
**AND** the audit log records `action: jira_config_enabled`

---

### Export Sync Logs

**WHEN** `GET /api/v1/admin/integrations/jira/{config_id}/sync-logs` is called with optional `?status=failed&work_item_id=`
**THEN** paginated sync log entries are returned
**AND** each entry includes `{work_item_id, jira_issue_key, status, error_message, attempt_count, last_attempt_at}`

---

### Manual Export Retry

**WHEN** a member with `retry_exports` capability submits `POST /api/v1/admin/integrations/jira/sync-logs/{log_id}/retry`
**THEN** a new Celery export task is queued for the element
**AND** `attempt_count` is incremented and `status` transitions to `retrying`
**AND** `triggered_by` is set to the requesting member ID
**AND** the audit log records `action: jira_export_retried`, `log_id`, `work_item_id`, `actor`

**WHEN** the sync log entry has `status: success`
**THEN** rejected with `409 Conflict` and `error.code: already_synced`

**WHEN** the Jira config associated with the log is in `disabled` or `error` state
**THEN** rejected with `409 Conflict` and `error.code: integration_unavailable`

---

## Error Handling Matrix

| Scenario | Behavior |
|---|---|
| Credentials invalid at test time | `auth_failure` — config stays `active` but `last_health_check_status: auth_failure` |
| Jira unreachable for 3+ consecutive health checks | Config transitions to `error`; SSE alert to integration/dashboard admins |
| Export task fails (network) | Automatic Celery retry up to 3 times with exponential backoff; then `status: failed` |
| Export fails (Jira API error 400/422) | No retry (bad request); `status: failed`; `error_message` stored |
| Config deleted while exports pending | Pending export tasks fail gracefully with `config_not_found`; log updated |
| Jira project key mapping deleted | Future exports for elements in that project use `default_jira_project_key` as fallback; if none, export fails with `no_mapping` |

---

## Security Constraints

- Credentials are NEVER returned in any API response (GET or PATCH).
- GET `/api/v1/admin/integrations/jira/{config_id}` returns config metadata without `credentials_ref`.
- Audit log entries for credential changes contain only `config_id` and actor — no token values.
- The secrets store key rotation is out of scope but the `credentials_ref` field design supports it. ⚠️ originally MVP-scoped — see decisions_pending.md

---

## API Endpoints Summary

| Method | Path | Required Capability |
|---|---|---|
| `POST` | `/api/v1/admin/integrations/jira` | `configure_integration` |
| `GET` | `/api/v1/admin/integrations/jira` | `configure_integration` or `view_admin_dashboard` |
| `GET` | `/api/v1/admin/integrations/jira/{id}` | `configure_integration` or `view_admin_dashboard` |
| `PATCH` | `/api/v1/admin/integrations/jira/{id}` | `configure_integration` |
| `POST` | `/api/v1/admin/integrations/jira/{id}/test` | `configure_integration` |
| `POST` | `/api/v1/admin/integrations/jira/{id}/mappings` | `configure_integration` |
| `GET` | `/api/v1/admin/integrations/jira/{id}/mappings` | `configure_integration` or `view_admin_dashboard` |
| `GET` | `/api/v1/admin/integrations/jira/{id}/sync-logs` | `configure_integration` or `view_admin_dashboard` |
| `POST` | `/api/v1/admin/integrations/jira/sync-logs/{log_id}/retry` | `retry_exports` |
