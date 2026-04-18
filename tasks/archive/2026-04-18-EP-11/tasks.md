# EP-11 — Implementation Checklist

**Epic**: EP-11 — Export & Sync with Jira
**Date**: 2026-04-13 (archived 2026-04-18)
**Status (MVP scope)**: ✅ SHIPPED — JiraClient (PAT + retry 2x + error hierarchy) + ExportService + `POST /api/v1/work-items/{id}/export/jira` + BackgroundTasks + migration 0118 `external_jira_key` + dual-write backcompat + audit queued/completed + FE export button (14 BE + 9 unit + 9 FE tests).

> **⚠️ Plan below is the pre-MVP plan from 2026-04-13 and is OBSOLETE.** The decisions recorded in `decisions_pending.md` #5, #12, #26 narrowed EP-11 to single-item export only: no polling, no webhooks, no `sync_logs`, no `SyncService` / `sync_task` / Celery Beat. Do not consider the unchecked boxes below as "pending work" — they describe work that was intentionally cut.
>
> **What v2 (full bi-directional sync) would add** — tracked as a future epic, NOT EP-11 scope:
> - Webhook listener for Jira → Tuio
> - Multi-workspace mapping rules
> - Issue-type mapping admin UI
> - `ImportService` per `specs/import/spec.md`

> **Scope (2026-04-14, decisions_pending.md #5/#12/#26)**: No polling, no webhooks, no `sync_logs`. Export is upsert-by-key (re-export UPDATEs the same Jira issue via `jira_issue_key`). Inbound is a user-initiated `POST /work-items/import-from-jira` action. `SyncService` / `sync_task` / Celery Beat below are **obsolete** — drop during TDD, replace with `ImportService` per `specs/import/spec.md`.

---

## Phase 1 — Data Model & Domain

### 1.1 Database migration

- [ ] Create migration: `integration_exports` table with all columns, indexes, and snapshot immutability trigger
- [ ] Verify: `idx_integration_exports_work_item`, `idx_integration_exports_status` (partial), `idx_integration_exports_syncable` (partial), `idx_integration_exports_jira_key` (partial)

### 1.2 Domain models

- [ ] [RED] Test: `WorkItemSnapshot` is immutable (frozen dataclass); cannot mutate after construction
- [ ] [GREEN] Implement `WorkItemSnapshot` value object in `domain/models/snapshot.py`
- [ ] [RED] Test: `IntegrationExport` entity — state transitions valid (pending→success, pending→failed, failed→retrying)
- [ ] [GREEN] Implement `IntegrationExport` with `ExportStatus` and `JiraDisplayStatus` enums in `domain/models/integration_export.py`
- [ ] [REFACTOR] Review for any leaking infrastructure concern

### 1.3 Repository interface

- [ ] Define `IntegrationExportRepository` interface in `domain/repositories/integration_export_repo.py`
  - `create`, `get`, `get_by_work_item`, `get_syncable`, `set_jira_ref`, `update_jira_status`, `set_status`

---

## Phase 2 — Infrastructure: Adapter & Persistence

### 2.1 Jira error hierarchy

- [ ] [RED] Test: `JiraErrorClassifier.classify()` returns correct error subclass for 401, 403, 404, 429, 500, timeout
- [ ] [GREEN] Implement `JiraApiError` hierarchy and `JiraErrorClassifier` in `infrastructure/adapters/jira/jira_error_classifier.py`

### 2.2 Jira API adapter

- [ ] [RED] Test: `JiraApiAdapter.create_issue()` returns `JiraIssueRef` on 201, raises typed error on each failure case (401, 403, 404, 429, 500, timeout) — use httpx mock transport
- [ ] [GREEN] Implement `JiraApiAdapter.create_issue()` in `infrastructure/adapters/jira/jira_api_adapter.py`
- [ ] [RED] Test: `JiraApiAdapter.get_issue_status()` returns `JiraIssueStatus` on 200, raises typed error on 401, 403, 404, 429, 5xx
- [ ] [GREEN] Implement `JiraApiAdapter.get_issue_status()`
- [ ] [REFACTOR] Confirm adapter has zero business logic — only HTTP and error classification

### 2.3 SQLAlchemy repository implementation

- [ ] [RED] Test: `IntegrationExportRepositoryImpl.create()` persists record and returns entity
- [ ] [RED] Test: `IntegrationExportRepositoryImpl.get_syncable()` returns only `status=success AND jira_status != done`
- [ ] [RED] Test: `IntegrationExportRepositoryImpl.set_jira_ref()` sets key, url, status=success, exported_at
- [ ] [GREEN] Implement `IntegrationExportRepositoryImpl` in `infrastructure/persistence/sqlalchemy/integration_export_repo_impl.py`

---

## Phase 3 — Application Services

### 3.1 SnapshotBuilder

- [ ] [RED] Test: `SnapshotBuilder.build()` captures all required fields from work item + sections
- [ ] [RED] Test: `SnapshotBuilder.build()` includes `has_override` and `override_justification` when present
- [ ] [RED] Test: `SnapshotBuilder.build()` produces valid `WorkItemSnapshot` with `captured_at` set to now
- [ ] [GREEN] Implement `SnapshotBuilder` in `application/mappers/snapshot_builder.py`

### 3.2 JiraFieldMapper

- [ ] [RED] Test: `JiraFieldMapper.map()` produces valid Jira fields dict with project key, issue type, summary
- [ ] [RED] Test: `JiraFieldMapper.map()` omits `assignee` when no account mapping exists
- [ ] [RED] Test: `JiraFieldMapper.map()` includes ADF description with all sections
- [ ] [RED] Test: `JiraFieldMapper.map()` appends override note to description when `has_override=True`
- [ ] [GREEN] Implement `JiraFieldMapper` in `application/mappers/jira_field_mapper.py`

### 3.3 JiraStatusMapper

- [ ] [RED] Test: `JiraStatusMapper.map()` returns `open` for category key `new`
- [ ] [RED] Test: `JiraStatusMapper.map()` returns `in_progress` for `indeterminate`
- [ ] [RED] Test: `JiraStatusMapper.map()` returns `done` for `done`
- [ ] [RED] Test: `JiraStatusMapper.map()` returns `unknown` for unmapped keys
- [ ] [GREEN] Implement `JiraStatusMapper` in `application/mappers/jira_status_mapper.py`

### 3.4 ReadyGate & IdempotencyGuard

- [ ] [RED] Test: `ReadyGate.check()` raises `ElementNotReadyError` when state != ready
- [ ] [RED] Test: `ReadyGate.check()` passes silently when state = ready
- [ ] [GREEN] Implement `ReadyGate` in `application/validators/ready_gate.py`
- [ ] [RED] Test: `IdempotencyGuard.check_in_progress()` raises `ExportAlreadyInProgressError` when pending/retrying export exists
- [ ] [RED] Test: `IdempotencyGuard.check_jira_key_set()` returns True when jira_issue_key already set on export
- [ ] [GREEN] Implement `IdempotencyGuard` in `application/validators/idempotency_guard.py`

### 3.5 ExportService

- [ ] [RED] Test: `ExportService.trigger_export()` raises `ElementNotReadyError` when not ready
- [ ] [RED] Test: `ExportService.trigger_export()` raises `JiraConfigNotFoundError` when no active config
- [ ] [RED] Test: `ExportService.trigger_export()` raises `JiraConfigDegradedError` when config.state = error
- [ ] [RED] Test: `ExportService.trigger_export()` raises `JiraMappingNotFoundError` when no project mapping
- [ ] [RED] Test: `ExportService.trigger_export()` raises `ExportAlreadyInProgressError` on duplicate trigger
- [ ] [RED] Test: `ExportService.trigger_export()` creates export record + dispatches Celery task on valid input
- [ ] [RED] Test: `ExportService.retry_export()` raises on non-failed export status
- [ ] [RED] Test: `ExportService.retry_export()` sets status=retrying and dispatches task for failed export
- [ ] [GREEN] Implement `ExportService` in `application/services/export_service.py`

### 3.6 ImportService (replaces SyncService — decision #12)

- [ ] [RED] Test: `ImportService.import_from_jira(key, project_id, workspace_id)` creates a `draft` work_item with `imported_from_jira=true`, `jira_source_key=<key>`
- [ ] [RED] Test: raises `JiraConfigNotFoundError` when no active Jira config for workspace
- [ ] [RED] Test: raises `JiraNotFoundError` when Jira issue does not exist
- [ ] [RED] Test: raises `AlreadyImportedError` (409) with existing `work_item_id` when another workspace work_item already has the same `jira_source_key`
- [ ] [RED] Test: audit event `work_item.imported` recorded
- [ ] [GREEN] Implement `ImportService` in `application/services/import_service.py`
- [ ] See `specs/import/spec.md` for full scenarios

### 3.7 Divergence detection

- [ ] [RED] Test: `DivergenceChecker.is_diverged()` returns False when no successful export exists
- [ ] [RED] Test: `DivergenceChecker.is_diverged()` returns False when version_id matches latest export
- [ ] [RED] Test: `DivergenceChecker.is_diverged()` returns True when version_id differs from latest export
- [ ] [GREEN] Implement `DivergenceChecker` in `application/services/export_service.py` (inline — no extra class needed)

---

## Phase 4 — Celery Tasks

### 4.1 ExportTask

- [ ] [RED] Test: task skips Jira call and marks success when jira_issue_key already set (Layer 2 idempotency)
- [ ] [RED] Test: task calls adapter, sets jira_ref, records audit on success
- [ ] [RED] Test: task marks failed + does NOT retry on JiraAuthError (401)
- [ ] [RED] Test: task marks failed + does NOT retry on JiraPermissionError (403)
- [ ] [RED] Test: task marks failed + does NOT retry on JiraNotFoundError (404)
- [ ] [RED] Test: task retries with correct backoff on JiraRateLimitError (respects Retry-After)
- [ ] [RED] Test: task retries with exponential backoff on JiraServerError and JiraTimeoutError
- [ ] [RED] Test: task marks failed after max_retries exhausted
- [ ] [GREEN] Implement `export_task` in `infrastructure/tasks/export_task.py`

### 4.2 (Sync task removed — decision #26)

No Celery Beat, no polling. Import is synchronous from the API controller (one Jira GET + one DB insert).

---

## Phase 5 — Presentation Layer

### 5.1 Export controller

- [ ] [RED] Test: `POST /work-items/:id/export` returns 202 on valid request
- [ ] [RED] Test: `POST /work-items/:id/export` returns 422 for each blocking condition (5 scenarios)
- [ ] [RED] Test: `POST /work-items/:id/export` returns 409 on duplicate in-progress export
- [ ] [RED] Test: `GET /work-items/:id/exports` returns list with diverged flag
- [ ] [RED] Test: `GET /work-items/:id/exports` includes is_current_version per record
- [ ] [RED] Test: `POST /exports/:id/retry` returns 403 without RETRY_EXPORTS capability
- [ ] [RED] Test: `POST /exports/:id/retry` returns 422 if export status is not failed
- [ ] [RED] Test: `POST /exports/:id/retry` returns 202 on valid retry
- [ ] [GREEN] Implement `ExportController` in `presentation/controllers/export_controller.py`

### 5.2 Import controller (decision #12)

- [ ] [RED] Test: `POST /work-items/import-from-jira` returns 201 with new work_item payload (state=draft, imported_from_jira=true, jira_source_key=<key>)
- [ ] [RED] Test: returns 422 `JIRA_CONFIG_NOT_FOUND` when workspace has no active Jira config
- [ ] [RED] Test: returns 422 `JIRA_ISSUE_NOT_FOUND` when key does not exist in Jira
- [ ] [RED] Test: returns 409 `ALREADY_IMPORTED` with existing `work_item_id` on duplicate import
- [ ] [GREEN] Implement `ImportController` in `presentation/controllers/import_controller.py`

---

## Phase 6 — Integration & Manual QA

- [ ] Integration test: full export flow against Jira sandbox (or WireMock stub of Jira API)
- [ ] Integration test: re-export updates the same Jira issue (upsert-by-key), not a new issue
- [ ] Integration test: retry flow succeeds after simulated 500 on first attempt
- [ ] Integration test: `POST /work-items/import-from-jira` creates draft work_item from a stubbed Jira issue
- [ ] Manual QA: export blocked for non-Ready element — verify 422 message
- [ ] Manual QA: export trigger → Jira issue visible → link shown in UI
- [ ] Manual QA: edit work item post-export → divergence indicator appears
- [ ] Manual QA: re-export after divergence → same Jira issue updated, divergence cleared
- [ ] Manual QA: import from Jira → draft work item appears; subsequent export updates the original issue

---

## Progress Tracking

Update checkboxes after each completed step. Mark phase complete with:
**Status: COMPLETED** (YYYY-MM-DD)

When all phases complete, archive to `tasks/archive/YYYY-MM-DD-EP-11/`.
