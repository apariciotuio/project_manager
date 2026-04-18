# EP-11 Backend Subtasks — Export & Sync with Jira

**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery
**Depends on**: EP-10 (jira_configs, jira_project_mappings, credentials_store, JiraClient, AuditService), EP-04 (versioning, current_version_id on work_item), EP-12 (middleware, auth)

> **Scope (2026-04-14, decisions_pending.md #5/#12/#26)**: No polling, no webhooks, no `sync_logs`. Export is upsert-by-key (re-export UPDATEs the same Jira issue via `jira_issue_key`). Inbound is a user-initiated `POST /work-items/import-from-jira` action; no automated status sync. `SyncService`/`SyncTask`/`sync_all_active_exports` below are **obsolete** — drop during TDD, replace with `ImportService` + `import_from_jira` endpoint per `specs/import/spec.md`.

---

## API Contract (interface for frontend)

```
POST   /api/v1/work-items/{id}/export
       Body: {}
       Auth: authenticated member with read access to work item
       Response 202: { "export_id": "uuid", "status": "pending" }
       Response 422: { "error": { "code": "ELEMENT_NOT_READY" | "JIRA_CONFIG_NOT_FOUND" |
                                   "JIRA_CONFIG_DEGRADED" | "JIRA_PROJECT_MAPPING_NOT_FOUND",
                                   "message": "..." } }
       Response 409: { "error": { "code": "EXPORT_ALREADY_IN_PROGRESS",
                                   "export_id": "uuid" } }

GET    /api/v1/work-items/{id}/exports
       Auth: authenticated member with read access to work item
       Response 200: {
         "exports": [ExportRecord],
         "diverged": bool
       }
       ExportRecord: {
         id, jira_issue_key, jira_issue_url, status,
         exported_at, exported_by,
         jira_status,              -- open | in_progress | done | unknown | not_found
         jira_status_last_synced_at,
         version_id, is_current_version,
         error_code, attempt_count
       }

POST   /api/v1/exports/{id}/retry
       Auth: requires RETRY_EXPORTS capability (EP-10)
       Response 202: { "export_id": "uuid", "status": "retrying" }
       Response 403: missing RETRY_EXPORTS capability
       Response 404: export not found
       Response 422: export status is not 'failed'
```

---

## Group 1 — Migration & Schema

### Acceptance Criteria

WHEN the migration runs
THEN `integration_exports` table exists with columns: `id`, `work_item_id`, `version_id`, `snapshot_data` (JSONB), `jira_issue_key`, `jira_issue_url`, `status`, `jira_status`, `jira_status_last_synced_at`, `exported_at`, `exported_by`, `error_code`, `error_detail`, `attempt_count`
AND partial index `idx_integration_exports_status` covers only `status IN ('pending', 'retrying')`
AND partial index `idx_integration_exports_syncable` covers `status = 'success' AND jira_status != 'done'`
AND the PostgreSQL rule `no_update_integration_exports_snapshot` prevents any UPDATE to the `snapshot_data` column

WHEN the migration is rolled back
THEN `integration_exports` table is dropped cleanly with no constraint errors

## Group 1 — Migration & Schema

- [ ] [RED] Write test asserting `integration_exports` table exists with all columns
- [ ] [RED] Write test asserting partial indexes exist: `idx_integration_exports_status`, `idx_integration_exports_syncable`, `idx_integration_exports_jira_key`
- [ ] [GREEN] Create migration: `integration_exports` table with all columns (see design.md section 2)
- [ ] [GREEN] Add PostgreSQL rule: `no_update_integration_exports_snapshot` (snapshot immutability)
- [ ] [GREEN] Add indexes: `idx_integration_exports_work_item`, `idx_integration_exports_status` (partial: pending/retrying), `idx_integration_exports_syncable` (partial: success, jira_status != done), `idx_integration_exports_jira_key`
- [ ] [REFACTOR] Include EXPLAIN ANALYZE output on 3 most frequent queries as migration comments (EP-12 requirement)

---

## Group 2 — Domain Models

- [ ] [RED] Test: `WorkItemSnapshot` is a frozen dataclass — any mutation attempt raises `FrozenInstanceError`
- [ ] [RED] Test: `WorkItemSnapshot` requires `captured_at` to be set on construction; cannot be None
- [ ] [GREEN] Implement `WorkItemSnapshot` in `domain/models/snapshot.py` (frozen dataclass, all fields from design.md section 2)
- [ ] [RED] Test: `IntegrationExport` state transitions — valid: pending→success, pending→failed, failed→retrying; invalid: success→retrying (rejected)
- [ ] [GREEN] Implement `IntegrationExport` entity with `ExportStatus` enum (pending|success|failed|retrying) and `JiraDisplayStatus` enum (open|in_progress|done|unknown|not_found) in `domain/models/integration_export.py`
- [ ] [REFACTOR] Verify no infrastructure import in domain models (no httpx, no SQLAlchemy, no Celery)

### Repository Interface
- [ ] Define `IntegrationExportRepository` in `domain/repositories/integration_export_repo.py`:
  - `create(export: IntegrationExport) -> IntegrationExport`
  - `get(export_id: UUID) -> IntegrationExport | None`
  - `get_by_work_item(work_item_id: UUID) -> list[IntegrationExport]`
  - `get_in_progress(work_item_id: UUID) -> IntegrationExport | None`
  - `get_syncable(batch_size: int, offset: int = 0) -> list[IntegrationExport]`
  - `set_jira_ref(export_id: UUID, key: str, url: str) -> None`
  - `update_jira_status(export_id: UUID, jira_status: JiraDisplayStatus) -> None`
  - `set_status(export_id: UUID, status: ExportStatus, error_code?: str, error_detail?: str) -> None`

---

## Group 3 — Infrastructure: Jira API Adapter & Error Handling

### Acceptance Criteria — Jira Error Matrix

WHEN Jira API returns HTTP 401
THEN `JiraErrorClassifier.classify()` returns `JiraAuthError`
AND the export task marks status=`failed` and does NOT retry

WHEN Jira API returns HTTP 403
THEN classifier returns `JiraPermissionError`
AND the export task marks status=`failed` and does NOT retry

WHEN Jira API returns HTTP 404
THEN classifier returns `JiraNotFoundError`
AND the export task marks status=`failed` and does NOT retry
AND `jira_config.consecutive_failures` is NOT incremented

WHEN Jira API returns HTTP 429
THEN classifier returns `JiraRateLimitError` with `retry_after` parsed from `Retry-After` header (or None if absent)
AND the export task schedules retry using `retry_after` value if present, else standard exponential backoff

WHEN Jira API returns HTTP 500/502/503/504
THEN classifier returns `JiraServerError`
AND the export task retries with exponential backoff: 60s, 120s, 240s (max 3 retries)
AND each failure increments `jira_config.consecutive_failures`

WHEN httpx raises `TimeoutException`
THEN classifier returns `JiraTimeoutError`
AND the export task treats it identically to `JiraServerError` (retries same backoff)

WHEN `JiraApiAdapter.create_issue()` is called with a valid snapshot and mapping
THEN it calls `POST /rest/api/3/issue` and returns `JiraIssueRef(key, url)` on HTTP 201
AND the adapter contains zero business logic (only HTTP call + error classification)

### JiraApiError Hierarchy
- [ ] [RED] Test: `JiraErrorClassifier.classify(response)` returns correct subclass for 401 → `JiraAuthError`, 403 → `JiraPermissionError`, 404 → `JiraNotFoundError`, 429 → `JiraRateLimitError` (with `retry_after` from header), 500 → `JiraServerError`, httpx.TimeoutException → `JiraTimeoutError`
- [ ] [GREEN] Implement error hierarchy in `infrastructure/adapters/jira/jira_error_classifier.py`

### JiraClient (MVP — single-issue creation, EP-11 slice 1)
- [x] [RED] Tests for `JiraClient.create_issue()` — 201→JiraIssue, 400→JiraValidationError, 429→JiraRateLimited(retry_after), 5xx retry 2x→JiraUnavailable, ADF body — `tests/unit/infrastructure/adapters/test_jira_adapter.py` (10 tests)
- [x] [GREEN] Implement `JiraClient` in `infrastructure/adapters/jira_adapter.py` — PAT auth, httpx.AsyncClient, timeout 30s, 2 retries exponential backoff, ADF wrapping
- [x] [GREEN] `JiraSettings` updated with `email`, `api_token` (SecretStr), prod validator for sentinel `dev-jira-token`
- [x] [GREEN] `ExportService.export_work_item_to_jira()` in `application/services/export_service.py` — type mapping, calls JiraClient, persists via `export_reference`, emits audit
- [x] [GREEN] `external_jira_key` column + mapper + schema — migration 0118 (`backend/migrations/versions/0118_work_items_external_jira_key.py`); dual-writes `export_reference` for backward compat (drop in next release); 5 unit tests in `tests/unit/application/test_export_service.py`
- [x] [GREEN] `POST /api/v1/work-items/{id}/export/jira` in `integration_controller.py` — 202 + BackgroundTask, auth+workspace guard
- [x] [RED+GREEN] Controller tests: 202 on valid, 401 no auth, 401 no workspace, 422 missing project_key — `tests/integration/test_export_controller.py` (4 tests)

### JiraApiAdapter
- [ ] [RED] Test: `JiraApiAdapter.create_issue()` — returns `JiraIssueRef(key, url)` on 201; raises `JiraAuthError` on 401; raises `JiraPermissionError` on 403; raises `JiraNotFoundError` on 404; raises `JiraRateLimitError` on 429; raises `JiraServerError` on 5xx; raises `JiraTimeoutError` on timeout — use httpx mock transport
- [ ] [GREEN] Implement `JiraApiAdapter.create_issue()` in `infrastructure/adapters/jira/jira_api_adapter.py`
- [ ] [RED] Test: `JiraApiAdapter.get_issue_status()` — returns `JiraIssueStatus(key, status_category_key, status_name)` on 200; raises typed errors for 401/403/404/429/5xx
- [ ] [GREEN] Implement `JiraApiAdapter.get_issue_status()`
- [ ] [REFACTOR] Assert adapter contains zero business logic — only HTTP calls and error classification

### SQLAlchemy Repository Implementation
- [ ] [RED] Test: `create()` persists record, returns entity with generated ID
- [ ] [RED] Test: `get_syncable()` returns only records where `status=success AND jira_status != done`
- [ ] [RED] Test: `set_jira_ref()` atomically sets `jira_issue_key`, `jira_issue_url`, `status=success`, `exported_at=now()`
- [ ] [GREEN] Implement `IntegrationExportRepositoryImpl` in `infrastructure/persistence/sqlalchemy/integration_export_repo_impl.py`

---

## Group 4 — Application Services

### SnapshotBuilder
- [ ] [RED] Test: `build()` captures all required fields: work_item + sections; `captured_at` is set to current time
- [ ] [RED] Test: `build()` includes `has_override=True` and `override_justification` when override present
- [ ] [RED] Test: `build()` produces immutable `WorkItemSnapshot` (frozen)
- [ ] [GREEN] Implement `SnapshotBuilder` in `application/mappers/snapshot_builder.py`

### JiraFieldMapper
- [ ] [RED] Test: `map()` produces valid fields dict with `project.key`, `issuetype.id`, `summary`, `description` (ADF)
- [ ] [RED] Test: `map()` omits `assignee` when no `assignee_account_id_map` entry exists for the assignee
- [ ] [RED] Test: `map()` includes ADF description with all sections in order
- [ ] [RED] Test: `map()` appends override note section to ADF description when `has_override=True`
- [ ] [GREEN] Implement `JiraFieldMapper` in `application/mappers/jira_field_mapper.py`

### JiraStatusMapper
- [ ] [RED] Test: `new` → `open`, `indeterminate` → `in_progress`, `done` → `done`, unknown string → `unknown`
- [ ] [GREEN] Implement `JiraStatusMapper` in `application/mappers/jira_status_mapper.py`

### ReadyGate & IdempotencyGuard
- [ ] [RED] Test: `ReadyGate.check()` raises `ElementNotReadyError` when `state != ready`; passes silently when `state = ready`
- [ ] [GREEN] Implement `ReadyGate` in `application/validators/ready_gate.py`
- [ ] [RED] Test: `IdempotencyGuard.check_in_progress()` raises `ExportAlreadyInProgressError` when pending/retrying export exists for work_item_id
- [ ] [RED] Test: `IdempotencyGuard.check_jira_key_set()` returns `True` when `jira_issue_key` already populated on export
- [ ] [GREEN] Implement `IdempotencyGuard` in `application/validators/idempotency_guard.py`

### Acceptance Criteria — ExportService & IdempotencyGuard

WHEN `trigger_export()` is called for a work item with state != `ready`
THEN `ElementNotReadyError` is raised and NO export record is created

WHEN `trigger_export()` is called and no active Jira config exists
THEN `JiraConfigNotFoundError` is raised

WHEN `trigger_export()` is called and the Jira config has state=`error`
THEN `JiraConfigDegradedError` is raised

WHEN `trigger_export()` is called and no project mapping exists for the work item's project
THEN `JiraMappingNotFoundError` is raised

WHEN `trigger_export()` is called and an export with status `pending` or `retrying` already exists for the work item
THEN `ExportAlreadyInProgressError` is raised with the existing `export_id`

WHEN `trigger_export()` is called with all preconditions met
THEN an export record with `status=pending` is persisted in the same DB transaction
AND a Celery task is dispatched AFTER the transaction commits

WHEN `retry_export()` is called for an export with status != `failed`
THEN it raises an error mapped to HTTP 422

WHEN `retry_export()` is called for a `failed` export
THEN `snapshot_data` is NOT rebuilt — the original snapshot is reused
AND the export `status` is set to `retrying` and a new Celery task is dispatched

### ExportService
- [ ] [RED] Test: `trigger_export()` raises `ElementNotReadyError` when state != ready
- [ ] [RED] Test: `trigger_export()` raises `JiraConfigNotFoundError` when no active config for workspace
- [ ] [RED] Test: `trigger_export()` raises `JiraConfigDegradedError` when config.state = error
- [ ] [RED] Test: `trigger_export()` raises `JiraMappingNotFoundError` when no project mapping exists
- [ ] [RED] Test: `trigger_export()` raises `ExportAlreadyInProgressError` on duplicate trigger
- [ ] [RED] Test: `trigger_export()` creates export record with status=pending AND dispatches Celery task on valid input
- [ ] [RED] Test: `retry_export()` raises 422 when export status is not failed
- [ ] [RED] Test: `retry_export()` sets status=retrying and dispatches task for failed export; reuses original snapshot_data (NOT rebuilt)
- [ ] [GREEN] Implement `ExportService` in `application/services/export_service.py`

### Acceptance Criteria — DivergenceChecker

WHEN no successful export exists for a work item
THEN `diverged = False` (no reference snapshot to diverge from)

WHEN the latest successful export has `version_id` matching `work_item.current_version_id`
THEN `diverged = False`

WHEN the latest successful export has a `version_id` that differs from `work_item.current_version_id`
THEN `diverged = True`
AND the `GET /api/v1/work-items/{id}` response includes `diverged: true`
AND `GET /api/v1/work-items/{id}/exports` includes `is_current_version: false` on the stale record

WHEN a re-export succeeds (new export with new version_id)
THEN `diverged = False` for subsequent calls
AND the old export record remains queryable with its original `version_id`

### DivergenceChecker
- [ ] [RED] Test: returns `False` when no successful export exists
- [ ] [RED] Test: returns `False` when latest export version_id matches work_item.current_version_id
- [ ] [RED] Test: returns `True` when version_id differs from latest successful export
- [ ] [GREEN] Implement as inline method in `ExportService` (no separate class needed)

### ImportService (replaces SyncService — decision #12)
- [ ] [RED] Test: `import_from_jira(jira_issue_key, project_id, workspace_id)` fetches issue via `JiraApiAdapter.get_issue()`, creates new `work_item` in `draft` state with `imported_from_jira=True` and `jira_source_key=<key>`
- [ ] [RED] Test: raises `JiraConfigNotFoundError` when no active config for workspace
- [ ] [RED] Test: raises `JiraNotFoundError` (maps to 422) when issue does not exist
- [ ] [RED] Test: duplicate import detection — if a work_item with matching `jira_source_key` already exists in the workspace, raises `AlreadyImportedError` (maps to 409) with existing `work_item_id`
- [ ] [RED] Test: import audits `work_item.imported` in `audit_events`
- [ ] [GREEN] Implement `ImportService` in `application/services/import_service.py`
- [ ] [GREEN] Extend `JiraApiAdapter` with `get_issue(key)` returning a minimal payload (summary, description ADF, issue_type, status) sufficient to populate a `draft` work item
- [ ] See `specs/import/spec.md` for full scenarios

---

## Group 5 — Celery Tasks

### Acceptance Criteria — ExportTask (Retry Behavior & Idempotency)

WHEN the task executes and `jira_issue_key` is already set on the export record (Layer 2 idempotency)
THEN the Jira API call is skipped
AND the export is marked `success` without creating a duplicate Jira issue

WHEN the task succeeds on retry after a previous transient failure
THEN `jira_config.consecutive_failures` is reset to 0

WHEN `max_retries=3` is exhausted
THEN `integration_exports.status = 'failed'` with the appropriate `error_code`
AND the task does NOT raise an unhandled exception (Celery marks it complete)

WHEN the task is processing and the worker crashes (`acks_late=True`)
THEN the task is redelivered to another worker
AND the Layer 2 idempotency check prevents a duplicate Jira issue

### ExportTask (`infrastructure/tasks/export_task.py`)
- [ ] [RED] Test: skips Jira API call and marks success when `jira_issue_key` already set (Layer 2 idempotency)
- [ ] [RED] Test: calls adapter then calls `ExportService.mark_export_success(export_id, jira_ref)` — the task must NOT call `AuditService.record()` directly; audit is the ExportService's responsibility (Fixed per backend_review.md LV-5)
- [ ] [RED] Test: marks failed + does NOT retry on `JiraAuthError` (401)
- [ ] [RED] Test: marks failed + does NOT retry on `JiraPermissionError` (403)
- [ ] [RED] Test: marks failed + does NOT retry on `JiraNotFoundError` (404)
- [ ] [RED] Test: retries with `Retry-After` header value as countdown on `JiraRateLimitError`; falls back to standard backoff if header absent
- [ ] [RED] Test: retries with exponential backoff on `JiraServerError` and `JiraTimeoutError` (60s, 120s, 240s)
- [ ] [RED] Test: marks failed after `max_retries=3` exhausted
- [ ] [RED] Test: task raises `SoftTimeLimitExceeded` when Jira call hangs → export is marked `failed` with `error_code=JIRA_TIMEOUT` and does NOT retry (Fixed per backend_review.md CA-3)
- [ ] [GREEN] Implement `export_task` with `acks_late=True`, `reject_on_worker_lost=True`, `max_retries=3`, `soft_time_limit=45` (guards against hung Jira connections; `SoftTimeLimitExceeded` must be caught, export marked failed, no retry)
- [ ] [GREEN] Update `jira_config.consecutive_failures` on auth/permission/server errors; reset on success

### (Sync task removed — decision #26)
No Celery Beat, no polling. Import is synchronous from the API controller (single Jira GET + one DB insert).

---

## Group 6 — Presentation Layer

### Acceptance Criteria

WHEN `POST /api/v1/work-items/{id}/export` is called for a ready work item with valid config and mapping
THEN the response is HTTP 202 with `{export_id: uuid, status: "pending"}`

WHEN `POST /api/v1/work-items/{id}/export` is called and state != ready
THEN the response is HTTP 422 with `error.code: ELEMENT_NOT_READY`; no Celery task is dispatched

WHEN `POST /api/v1/work-items/{id}/export` is called with no active Jira config
THEN the response is HTTP 422 with `error.code: JIRA_CONFIG_NOT_FOUND`

WHEN `POST /api/v1/work-items/{id}/export` is called with config in `error` state
THEN the response is HTTP 422 with `error.code: JIRA_CONFIG_DEGRADED`

WHEN `POST /api/v1/work-items/{id}/export` is called with no project mapping
THEN the response is HTTP 422 with `error.code: JIRA_PROJECT_MAPPING_NOT_FOUND`

WHEN `POST /api/v1/work-items/{id}/export` is called while an export is already `pending` or `retrying`
THEN the response is HTTP 409 with `error.code: EXPORT_ALREADY_IN_PROGRESS` and `{export_id}` in the body

WHEN `GET /api/v1/work-items/{id}/exports` is called
THEN the response includes `{exports: [...], diverged: bool}`
AND each export record includes `is_current_version: bool`

WHEN `POST /api/v1/exports/{id}/retry` is called without `RETRY_EXPORTS` capability
THEN the response is HTTP 403

WHEN `POST /api/v1/exports/{id}/retry` is called for a non-`failed` export
THEN the response is HTTP 422

WHEN `POST /api/v1/exports/{id}/retry` is called for a `failed` export with correct capability
THEN the response is HTTP 202 with `{export_id, status: "retrying"}`

WHEN any export endpoint is called without authentication
THEN the response is HTTP 401

WHEN any export endpoint is called for a work item outside the user's scope
THEN the response is HTTP 404 (not 403 — do not leak item existence)

## Group 6 — Presentation Layer

- [ ] [RED] Test: `POST /work-items/{id}/export` returns 202 on valid request
- [ ] [RED] Test: returns 422 for each of 5 blocking conditions (not ready, no config, degraded config, no mapping)
- [ ] [RED] Test: returns 409 on duplicate in-progress export with `export_id` in response body
- [ ] [RED] Test: `GET /work-items/{id}/exports` returns list with `diverged` flag and `is_current_version` per record
- [ ] [RED] Test: `POST /exports/{id}/retry` returns 403 without `RETRY_EXPORTS` capability
- [ ] [RED] Test: `POST /exports/{id}/retry` returns 422 if export status is not failed
- [ ] [RED] Test: `POST /exports/{id}/retry` returns 202 on valid retry
- [ ] [GREEN] Implement `ExportController` in `presentation/controllers/export_controller.py`
- [ ] All endpoints: 401 if no auth, 403 if insufficient scope, 404 if work_item not accessible to user

### Import Controller (decision #12)

- [ ] [RED] Test: `POST /work-items/import-from-jira` returns 201 with new work_item (state=draft, imported_from_jira=true, jira_source_key=<key>)
- [ ] [RED] Test: returns 422 `JIRA_CONFIG_NOT_FOUND` when workspace has no active Jira config
- [ ] [RED] Test: returns 422 `JIRA_ISSUE_NOT_FOUND` when key does not exist in Jira
- [ ] [RED] Test: returns 409 `ALREADY_IMPORTED` with existing `work_item_id` on duplicate import
- [ ] [RED] Test: 403 if caller lacks `create_work_item` capability for the target project
- [ ] [GREEN] Implement `ImportController` in `presentation/controllers/import_controller.py`

---

## Group 7 — Integration Tests

- [ ] Integration test: full export flow against WireMock stub of Jira API (trigger → task runs → jira_key set → success status)
- [ ] Integration test: re-export updates the same Jira issue (upsert-by-key — PUT /rest/api/3/issue/{key}), not a new issue
- [ ] Integration test: retry flow — simulate 500 on first attempt, success on retry
- [ ] Integration test: Layer 2 idempotency — crash after Jira call but before DB update; re-run task; assert no duplicate Jira issue
- [ ] Integration test: `diverged=true` after editing work item post-export
- [ ] Integration test: re-export clears divergence (new export version_id matches current)
- [ ] Integration test: `POST /work-items/import-from-jira` creates a `draft` work item with `imported_from_jira=true`, `jira_source_key=<key>`; subsequent export upserts the original Jira issue
