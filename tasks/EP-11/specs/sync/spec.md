# EP-11 Sync Spec — US-113, US-114

**Epic**: EP-11 — Export & Sync with Jira
**Capability**: Jira status polling, status mapping, post-export element behavior, divergence detection
**Stories**: US-113, US-114
**Date**: 2026-04-13

---

## US-113 — Sync Basic Status from Jira

### Polling Mechanism

**Scenario: Periodic sync task runs for all active exports**

WHEN the Celery periodic sync task executes (default interval: every 15 minutes)
THEN it queries integration_exports where status = `success` AND jira_status != `done`
AND for each record, calls `GET /rest/api/3/issue/{jira_issue_key}?fields=status` on the relevant jira_config
AND updates integration_exports.jira_status with the mapped internal status
AND updates integration_exports.jira_status_last_synced_at to now()
AND logs the sync attempt in jira_sync_logs

**Scenario: Sync skips exports linked to degraded Jira config**

WHEN the sync task processes a batch of exports
AND the associated jira_config has state = `error`
THEN the task skips all exports linked to that config
AND logs a skipped-due-to-config-error entry in jira_sync_logs
AND does NOT decrement or increment consecutive_failures (config health is managed by the health check task from EP-10)

**Scenario: Sync task handles Jira 401/403 on status fetch**

WHEN the sync task calls Jira and receives HTTP 401 or 403
THEN it logs error_code = `JIRA_AUTH_FAILURE` or `JIRA_PERMISSION_DENIED` in jira_sync_logs
AND increments jira_config.consecutive_failures
AND skips remaining exports for that config in this run
AND does NOT mark the integration_export as failed (sync failure != export failure)

**Scenario: Sync task handles Jira 429 or 5xx on status fetch**

WHEN the sync task receives HTTP 429 or 5xx while fetching a status
THEN it skips that specific issue for this polling cycle
AND logs the transient failure
AND relies on the next scheduled cycle for retry (no immediate backoff within the sync task)

**Scenario: Jira issue deleted or not found during sync**

WHEN the sync task calls Jira and receives HTTP 404 for a previously known jira_issue_key
THEN the task sets integration_exports.jira_status = `not_found`
AND logs error_code = `JIRA_ISSUE_DELETED`
AND does NOT attempt further sync for this export record until manually resolved

### Status Mapping

**Scenario: Jira status maps to internal display status**

WHEN the sync task receives a Jira status string
THEN it applies the following mapping:

| Jira Status Category | Internal Display Status |
|---|---|
| `To Do` (or equivalent) | `open` |
| `In Progress` (or equivalent) | `in_progress` |
| `Done` (or equivalent) | `done` |
| Any unmapped status string | `unknown` |

AND the mapping is based on Jira's `statusCategory.key` (not the status name, which is user-configurable)
AND status category keys: `new` → `open`, `indeterminate` → `in_progress`, `done` → `done`
AND `unknown` is stored when the status category key is not in the above set

**Scenario: Work item UI shows synced Jira status**

WHEN a user views an exported work item
THEN the UI shows the internal display status (open / in_progress / done / unknown / not_found)
AND the last sync timestamp is shown
AND a label clarifies this is the status in Jira, not the internal work item state

**Scenario: Sync does not trigger when no exports exist**

WHEN the sync task runs
AND no integration_exports records exist with status = `success`
THEN the task exits immediately with no Jira API calls made

---

## US-114 — Maintain Controlled Post-Export Behavior

### Post-Export Element Changes

**Scenario: Work item can be edited after export**

WHEN a work item has been successfully exported
THEN the work item remains fully editable (title, sections, metadata)
AND the internal FSM state transitions are not blocked by export status
AND no automatic update is sent to Jira
AND the existing integration_exports snapshot is NOT modified

**Scenario: Snapshot remains immutable after post-export changes**

WHEN a work item's content changes after export
THEN integration_exports.snapshot_data for the previous export is unchanged
AND integration_exports.version_id for the previous export still references the version at export time
AND a user can always retrieve the exact content that was sent to Jira

### Divergence Detection

**Scenario: Divergence detected when work item version changes after export**

WHEN a work item's current version_id differs from the version_id stored in the most recent integration_exports record
THEN the system marks the work item as having a divergent export
AND the UI displays a divergence indicator on the work item card and detail view
AND the divergence indicator shows when the export occurred and that the work item has since been modified
AND the indicator does NOT block any further work on the element

**Scenario: No divergence when work item has not changed since export**

WHEN a work item's current version_id matches the version_id in the most recent successful integration_exports record
THEN no divergence indicator is shown
AND the export is considered current

**Scenario: Divergence resolved by re-export**

WHEN a user exports a work item that has diverged from its last export
AND the work item is in Ready state at the time of re-export
THEN a new integration_exports record is created with the new version_id and new snapshot_data
AND the divergence indicator is cleared for the new export
AND the previous export record remains intact and queryable

**Scenario: Divergence indicator not shown on non-exported work items**

WHEN a work item has never been exported
THEN no divergence indicator is shown (there is no reference snapshot to diverge from)

### Re-Export Behavior

**Scenario: Re-export creates a new Jira issue (not an update)**

WHEN a user re-exports a diverged work item to Jira
THEN the system creates a NEW Jira issue (POST /rest/api/3/issue)
AND a new integration_exports record is created
AND the old Jira issue is NOT modified by the platform
AND the new Jira issue key is stored in the new integration_exports record
AND both Jira issues remain visible in the export history

**Scenario: Re-export blocked if element is not Ready**

WHEN a user attempts to re-export a work item that is not in Ready state
THEN the system blocks the export with HTTP 422 and error code `ELEMENT_NOT_READY`
AND this applies identically to first export and re-export (same validation path)

### Export History

**Scenario: User can view full export history for a work item**

WHEN a user requests GET /work-items/:id/exports
THEN the response includes all integration_exports records for that work item
AND each record shows: export_id, jira_issue_key, jira_issue_url, status, exported_at, exported_by, jira_status, version_id
AND records are ordered by exported_at DESC
AND failed exports are included in the history with their error details

**Scenario: Export history shows divergence state per record**

WHEN listing export history
THEN each record includes a `is_current_version` boolean
AND `is_current_version = true` only for the record whose version_id matches the work item's current version_id
AND at most one record has `is_current_version = true` at any time

---

## Out of Scope for This Capability

- Webhook-based Jira callbacks (MVP uses polling only)
- Two-way sync: writing changes from Jira back to the platform
- Automatic content updates pushed to Jira when the work item changes
- Re-opening or transitioning Jira issues from the platform
- Sync frequency configuration per workspace (fixed at 15 minutes for MVP)
