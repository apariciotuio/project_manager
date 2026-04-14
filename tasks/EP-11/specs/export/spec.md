# EP-11 Export Spec — US-110, US-111, US-112

**Epic**: EP-11 — Export & Sync with Jira
**Capability**: Export trigger, snapshot creation, Jira API call, reference storage
**Stories**: US-110, US-111, US-112
**Date**: 2026-04-13

---

## US-110 — Send to Jira via Explicit Action

### Trigger Validation

**Scenario: Export blocked for non-Ready element**

WHEN a user triggers export on a work item with state != `ready`
THEN the system returns HTTP 422 with error code `ELEMENT_NOT_READY`
AND the error message specifies the current state and the required state
AND no Jira API call is made
AND no export record is created

**Scenario: Export blocked when no Jira config exists**

WHEN a user triggers export on a Ready work item
AND no active Jira integration config exists for the workspace/project
THEN the system returns HTTP 422 with error code `JIRA_CONFIG_NOT_FOUND`
AND no Jira API call is made

**Scenario: Export blocked when Jira config is in error state**

WHEN a user triggers export on a Ready work item
AND the Jira config exists but has state = `error`
THEN the system returns HTTP 422 with error code `JIRA_CONFIG_DEGRADED`
AND the response includes the last health check failure reason
AND no Jira API call is made

**Scenario: Export blocked when no project mapping exists**

WHEN a user triggers export on a Ready work item
AND the work item belongs to a project with no Jira project mapping configured
THEN the system returns HTTP 422 with error code `JIRA_PROJECT_MAPPING_NOT_FOUND`
AND no Jira API call is made

**Scenario: Export blocked without RETRY_EXPORTS capability (on retry)**

WHEN a user without `RETRY_EXPORTS` capability attempts to retry a failed export
THEN the system returns HTTP 403
AND no Jira API call is made

**Scenario: Successful export trigger**

WHEN a user with appropriate access triggers export on a Ready work item
AND a valid Jira config and project mapping exist
THEN the system creates an integration_export record with state = `pending`
AND dispatches an async Celery task for the actual Jira API call
AND returns HTTP 202 with the export_id and status = `pending`

---

## US-111 — Build and Send Final Snapshot

### Snapshot Creation

**Scenario: Snapshot built from current version at time of export**

WHEN the export Celery task executes
THEN it reads the work item's current version_id at task execution time
AND captures a full snapshot of: title, description, sections (from EP-04), metadata, state, override flags, assignee, project context
AND stores the snapshot as JSONB in integration_exports.snapshot_data
AND the snapshot is linked to the specific version_id used

**Scenario: Snapshot is immutable after creation**

WHEN an integration_export record is created
THEN snapshot_data is written once and never updated
AND any subsequent changes to the work item do NOT modify snapshot_data
AND the version_id reference in integration_exports remains unchanged

**Scenario: Snapshot includes override metadata when present**

WHEN the work item reached Ready state via an override
THEN the snapshot includes `has_override: true` and `override_justification` in snapshot_data
AND this is included in the Jira issue description payload

### Jira API Call

**Scenario: Successful Jira issue creation**

WHEN the Celery task dispatches the Jira API call
THEN the system calls `POST /rest/api/3/issue` on the configured Jira base_url
AND the issue fields are mapped from the snapshot via the JiraFieldMapper
AND the Jira project key comes from jira_project_mappings for the work item's project
AND the issue type is determined by element_type_mappings in jira_project_mappings
AND on HTTP 201, the task writes jira_issue_key and jira_project_key to integration_exports
AND sets integration_exports.status = `success`
AND sets exported_at = now()

**Scenario: Jira field mapping**

WHEN constructing the Jira issue payload
THEN title maps to `summary` field
AND description sections map to `description` in Jira Document Format (ADF)
AND assignee maps to `assignee.accountId` if a Jira account mapping exists, otherwise omitted
AND work item metadata maps to configured custom fields per element_type_mappings
AND override_justification (if present) is appended as a note in the description

### Error Handling

**Scenario: Jira returns 401 (auth failure)**

WHEN the Jira API call returns HTTP 401
THEN the task marks integration_exports.status = `failed`
AND logs error_code = `JIRA_AUTH_FAILURE` with response body in jira_sync_logs
AND sets jira_config.state = `error` if consecutive_failures >= 3
AND does NOT retry automatically (credential issue — requires human intervention)
AND returns a notification-worthy event to SSE for workspace admins

**Scenario: Jira returns 403 (permission denied)**

WHEN the Jira API call returns HTTP 403
THEN the task marks integration_exports.status = `failed`
AND logs error_code = `JIRA_PERMISSION_DENIED`
AND does NOT retry automatically (permission issue — requires human intervention)
AND increments consecutive_failures on jira_config

**Scenario: Jira returns 404 (project not found)**

WHEN the Jira API call returns HTTP 404
THEN the task marks integration_exports.status = `failed`
AND logs error_code = `JIRA_PROJECT_NOT_FOUND`
AND does NOT retry automatically (mapping misconfiguration)
AND does NOT increment consecutive_failures (not a connectivity issue)

**Scenario: Jira returns 429 (rate limited)**

WHEN the Jira API call returns HTTP 429
THEN the task retries with exponential backoff: 60s, 120s, 240s (max 3 retries)
AND Retry-After header value is respected if present (takes precedence over backoff)
AND after 3 failed retries, marks integration_exports.status = `failed` with error_code = `JIRA_RATE_LIMITED`
AND does NOT modify jira_config.state (rate limiting is not a health degradation)

**Scenario: Jira returns 5xx (server error)**

WHEN the Jira API call returns HTTP 500, 502, 503, or 504
THEN the task retries with exponential backoff: 60s, 120s, 240s (max 3 retries)
AND increments consecutive_failures on jira_config after each failure
AND after 3 failed retries marks integration_exports.status = `failed` with error_code = `JIRA_SERVER_ERROR`
AND if jira_config.consecutive_failures >= 3, triggers SSE degradation alert

**Scenario: Network timeout**

WHEN the Jira API call times out (configurable, default 10s)
THEN the task treats it as a transient failure and retries using the same backoff as 5xx
AND logs error_code = `JIRA_TIMEOUT`

---

## US-112 — Store Jira Reference and Show Internal/External Link

### Reference Storage

**Scenario: Jira reference stored on successful export**

WHEN a Jira issue is created successfully
THEN integration_exports.jira_issue_key is set (e.g., "PROJ-123")
AND integration_exports.jira_project_key is set
AND integration_exports.jira_issue_url is derived from `{base_url}/browse/{jira_issue_key}`
AND the record is queryable by work_item_id

**Scenario: Multiple exports for the same work item**

WHEN a work item is exported more than once (e.g., after re-export following element evolution)
THEN each export creates a separate integration_exports record
AND the most recent successful export is the canonical reference
AND all historical exports remain queryable via GET /work-items/:id/exports
AND each integration_exports record is independently immutable

### Visibility

**Scenario: Jira link visible in work item view**

WHEN a user views a work item that has at least one successful export
THEN the UI displays the Jira issue key and a clickable link to the Jira issue
AND the link opens in a new tab
AND the last export date and exporter name are shown
AND if multiple exports exist, the most recent successful one is the primary display

**Scenario: Work item with no exports shows no Jira link**

WHEN a user views a work item that has never been exported
THEN no Jira link is displayed
AND the export action is available if the element is in Ready state

### Idempotency

**Scenario: Export triggered while a pending export already exists**

WHEN a user triggers export on a work item
AND integration_exports already has a record with status = `pending` or `retrying` for that work item
THEN the system returns HTTP 409 with error code `EXPORT_ALREADY_IN_PROGRESS`
AND no new export record is created
AND no new Celery task is dispatched

**Scenario: Celery task retry is idempotent**

WHEN the Celery task retries after a transient failure
AND jira_issue_key is already set on the integration_exports record (task succeeded on a previous attempt but response was lost)
THEN the task detects the existing key via pre-call idempotency check
AND skips the Jira API call
AND marks the export as success without creating a duplicate Jira issue

**Scenario: Manual retry of a failed export**

WHEN a user with `RETRY_EXPORTS` capability retries a failed export via POST /exports/:id/retry
THEN the system sets integration_exports.status = `retrying`
AND increments attempt_count
AND dispatches a new Celery task with the same snapshot_data (snapshot is NOT rebuilt)
AND the retry uses the same export_id as the idempotency key

---

## Out of Scope for This Capability

- Automatic or scheduled exports (EP-11 is explicit-action-only)
- Webhook-based Jira callbacks (MVP: polling only, covered in sync spec)
- Bulk export of multiple work items in one action
- Editing the Jira issue from within the platform post-export
- Custom field mapping UI (configured via project mappings, not per-export)
