# EP-11 Import Spec — User-initiated Import from Jira

> **Resolved 2026-04-14 (decisions_pending.md #12)**: User-initiated action that creates a work item in `draft` from an existing Jira issue. Not automated. Not triggered by polling or webhooks. Closes the loop with the upsert-by-key export: a later export of the imported work item UPDATEs the original Jira issue.

**Epic**: EP-11
**Endpoint**: `POST /api/v1/work-items/import-from-jira`
**Capability**: any workspace member with `can_import_from_jira` (Project Admin, Workspace Admin, Integration Admin, Superadmin). Members / Team Leads cannot import.

---

## Scenario: Happy path — import creates a Draft work item

WHEN a user POSTs `/api/v1/work-items/import-from-jira` with `{ jira_key: "PROJ-123", project_id: "<workspace project uuid>" }`
THEN the server resolves the Jira configuration for the project via `integration_project_mappings`.
AND calls `JiraApiAdapter.get_issue("PROJ-123")` to fetch title, description, issue type, status, assignee email, labels.
AND `JiraFieldMapper.to_work_item(issue, project_id)` maps the Jira issue to a draft work item with:
  - `title` ← Jira summary
  - `description` ← Jira description (rendered)
  - `type` ← mapped from Jira issue type (bug→bug, story→story, task→tarea, etc.)
  - `state` = `draft`
  - `original_input` = Jira description
  - `imported_from_jira` = true
  - `jira_source_key` = "PROJ-123"
  - `project_id` ← request input
  - `created_by` ← authenticated user
AND the work item is persisted.
AND an audit event `work_item.imported_from_jira` is written.
AND the server responds 201 `{ data: { work_item_id } }`.

---

## Scenario: Jira key already linked to an unresolved work item

WHEN the requested `jira_key` is already set as `jira_source_key` on an active (not terminal, not deleted) work item in the same workspace
THEN the server returns 409 `{ error: { code: "JIRA_KEY_ALREADY_LINKED", message: "PROJ-123 is already linked to work item <uuid>" } }`.
AND no new work item is created.

## Scenario: Jira issue not found

WHEN the Jira API responds 404 for the requested key
THEN the server returns 404 `{ error: { code: "JIRA_ISSUE_NOT_FOUND" } }`.

## Scenario: Jira auth failure / integration disabled

WHEN the Jira API responds 401/403, or the integration config is disabled
THEN the server returns 424 `{ error: { code: "JIRA_INTEGRATION_UNAVAILABLE" } }`.
AND writes an `integration.unavailable` audit event.

## Scenario: No mapping for the requested project

WHEN the requested `project_id` has no matching `integration_project_mappings` row
THEN the server returns 422 `{ error: { code: "NO_MAPPING", details: { project_id } } }`.

## Scenario: Capability check

WHEN the caller lacks `can_import_from_jira`
THEN the server returns 403 `{ error: { code: "FORBIDDEN" } }`.

## Scenario: Import closes the loop on later export

WHEN a user imports "PROJ-123" (creates work_item W)
AND later transitions W to Ready and exports it
THEN ExportService detects `W.jira_source_key = "PROJ-123"` and performs an UPDATE (not CREATE) against that Jira issue.
AND `jira_issue_key` on the export row equals `"PROJ-123"`.
AND the original Jira issue is updated in place — no duplicate issue is created.

## Scenario: Divergence warning at export after import

WHEN exporting an imported work item, and Jira `updated_at` for the issue is newer than `last_export_snapshot.captured_at` (or than the import snapshot if no export has happened yet)
THEN the server returns 409 `{ error: { code: "JIRA_DIVERGED", details: { local_version_id, jira_updated_at, per_field_diff } } }` unless `confirm_overwrite=true` is passed.
AND the diff is rendered with the EP-07 diff engine (`remark` + `diff-match-patch`).
