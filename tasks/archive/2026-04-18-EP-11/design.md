# EP-11 — Technical Design
## Jira: Export (upsert-by-key) + User-initiated Import

**Epic**: EP-11
**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery

> **Resolved 2026-04-14 (decisions_pending.md #5, #12, #26)**: No polling, no webhooks, no `sync_logs`, no status sync, no auto-sync. Export is upsert-by-key — the first export creates a Jira issue and stores `jira_issue_key`; subsequent exports UPDATE the same issue. New user-initiated **import** action creates a work item in `draft` from an existing Jira issue. Divergence is detected at export time (banner + per-field diff) but never blocks.

---

## 1. Architecture Overview

```
ExportController (user-initiated)
  └── ExportService
        ├── [VALIDATE] ReadyGate.check(work_item)
        ├── [VALIDATE] project mapping resolves to a jira_project_key (EP-10 integration_project_mappings)
        ├── [VALIDATE] capability `can_export` (Project Admin, Workspace Admin, Integration Admin, Superadmin — not Member/Team Lead)
        ├── [DIFF]     if work_item.jira_source_key or jira_issue_key already set: compare Jira `updated_at` vs last-export snapshot. If diverged, require `confirm_overwrite=true`.
        ├── [CREATE]   SnapshotBuilder.build(work_item)
        ├── [PERSIST]  IntegrationExportRepository.create(export, version_id)
        └── [DISPATCH] ExportTask.apply_async(export_id)

ExportTask (Celery queue `jira`)
  ├── [LOAD]    IntegrationExportRepository.get(export_id)
  ├── [UPSERT]  If jira_issue_key present (from prior export or import): UPDATE issue.
                Otherwise: CREATE issue and persist the returned key to the same row.
  └── [CALL]    ExportService.mark_export_success(export_id, jira_ref)

ImportController (user-initiated)
  └── ImportService
        ├── [VALIDATE] no unresolved work_item already linked to this jira_key
        ├── [CALL]    JiraApiAdapter.get_issue(jira_key)
        ├── [MAP]     JiraFieldMapper.to_work_item(jira_issue, project_id)
        └── [CREATE]  WorkItemService.create(imported_from_jira=true, jira_source_key=jira_key, state='draft')
```

No polling, no webhooks, no auto-sync task.

---

## 2. Data Model

### integration_exports

```sql
CREATE TABLE integration_exports (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id            UUID NOT NULL REFERENCES work_items(id),
    -- Per db_review.md DI-5: FK to work_item_versions prevents orphan snapshot references.
    -- ON DELETE RESTRICT because versions are immutable and exports pin specific versions.
    version_id              UUID NOT NULL REFERENCES work_item_versions(id) ON DELETE RESTRICT,
    jira_config_id          UUID NOT NULL REFERENCES jira_configs(id),
    jira_project_key        TEXT,                      -- set on success
    jira_issue_key          TEXT,                      -- set on success, e.g. "PROJ-123"
    jira_issue_url          TEXT,                      -- derived: {base_url}/browse/{key}
    jira_status             TEXT,                      -- open | in_progress | done | unknown | not_found
    jira_status_last_synced_at TIMESTAMPTZ,
    snapshot_data           JSONB NOT NULL,            -- immutable after INSERT
    status                  TEXT NOT NULL DEFAULT 'pending',  -- pending | success | failed | retrying
    error_code              TEXT,
    error_detail            TEXT,
    attempt_count           INT NOT NULL DEFAULT 0,
    exported_at             TIMESTAMPTZ,               -- set when status -> success
    exported_by             UUID REFERENCES users(id), -- users(id), NOT workspace_memberships (resolution #5)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- snapshot_data is write-once. Enforced by trigger:
CREATE RULE no_update_integration_exports_snapshot AS
    ON UPDATE TO integration_exports
    WHERE (OLD.snapshot_data IS NOT NULL AND NEW.snapshot_data != OLD.snapshot_data)
    DO INSTEAD NOTHING;

CREATE INDEX idx_integration_exports_work_item ON integration_exports(work_item_id, created_at DESC);
CREATE INDEX idx_integration_exports_status ON integration_exports(status) WHERE status IN ('pending', 'retrying');
CREATE INDEX idx_integration_exports_syncable ON integration_exports(jira_config_id, jira_status)
    WHERE status = 'success' AND jira_status != 'done';
CREATE INDEX idx_integration_exports_jira_key ON integration_exports(jira_issue_key) WHERE jira_issue_key IS NOT NULL;
```

### snapshot_data JSONB shape

```json
{
  "work_item_id": "uuid",
  "version_id": "uuid",
  "title": "string",
  "description": "string",
  "element_type": "string",
  "state": "ready",
  "has_override": false,
  "override_justification": null,
  "sections": [
    { "key": "string", "title": "string", "content": "string", "order": 0 }
  ],
  "assignee": { "id": "uuid", "name": "string", "email": "string" },
  "project": { "id": "uuid", "name": "string" },
  "workspace_id": "uuid",
  "captured_at": "ISO8601"
}
```

### Reuse from EP-10

`integration_configs`, `integration_project_mappings` are owned by EP-10 and reused as-is. EP-11 reads config and mapping; it does not mutate them except for `consecutive_failures` on the config (delegated through `IntegrationConfigRepository`).

**`sync_logs` table is removed** (resolution #26). All export audit lives in `audit_events`.

---

## 3. DDD Layer Breakdown

```
domain/
  models/
    integration_export.py     (IntegrationExport, ExportStatus, JiraDisplayStatus)
    snapshot.py               (WorkItemSnapshot — value object, immutable)
  repositories/
    integration_export_repo.py  (interface: create, get, get_syncable, set_jira_ref,
                                  update_jira_status, get_by_work_item)

application/
  services/
    export_service.py         (trigger_export, retry_export)
    sync_service.py           (sync_all_active_exports, sync_single)
  validators/
    ready_gate.py             (check_work_item_ready)
    idempotency_guard.py      (check_in_progress, check_jira_key_set)
  mappers/
    snapshot_builder.py       (build from work_item + sections + metadata)
    jira_field_mapper.py      (snapshot → Jira issue fields dict)
    jira_status_mapper.py     (statusCategory.key → JiraDisplayStatus)

presentation/
  controllers/
    export_controller.py      (POST /:id/export, GET /:id/exports, POST /exports/:id/retry)

infrastructure/
  persistence/
    sqlalchemy/
      integration_export_repo_impl.py
  adapters/
    jira/
      jira_api_adapter.py     (create_issue, get_issue_status — wraps httpx, raises typed errors)
      jira_error_classifier.py  (HTTP status → JiraApiError subclass)
  tasks/
    export_task.py            (Celery task: execute export, retry logic)
    sync_task.py              (Celery periodic: poll Jira for status updates)
```

---

## 4. Export Flow — Sequence Diagram

```
User                 ExportController      ExportService           DB              Celery          Jira
 |                        |                    |                    |                 |               |
 |-- POST /work-items/:id/export ------------> |                    |                 |               |
 |                        |-- validate_ready() |                    |                 |               |
 |                        |                    |-- get work_item -->|                 |               |
 |                        |                    |<-- work_item ------|                 |               |
 |                        |                    |-- check state (not ready?) -> 422    |               |
 |                        |                    |-- resolve_jira_config() ----------->|               |
 |                        |                    |-- check_in_progress() ------------->|               |
 |                        |                    |   (pending/retrying?) -> 409        |               |
 |                        |                    |-- build_snapshot(work_item)         |               |
 |                        |                    |-- INSERT integration_exports ------->|               |
 |                        |                    |<-- export_id ------------------------|               |
 |                        |                    |-- apply_async(export_task, export_id) ----------->  |
 |<-- 202 {export_id, status: pending} --------|                    |                 |               |
 |                        |                    |                    |                 |               |
 |                        |                    |                    |   [task runs]   |               |
 |                        |                    |                    |<-- load export  |               |
 |                        |                    |                    |                 |-- check key set? (idempotency)
 |                        |                    |                    |                 |-- map fields  |
 |                        |                    |                    |                 |-- POST /issue ----->
 |                        |                    |                    |                 |<------------ 201 {key}
 |                        |                    |                    |<-- set_jira_ref |               |
 |                        |                    |                    |<-- audit record |               |
```

---

## 5. Jira API Adapter

```python
class JiraApiAdapter:
    """Thin wrapper. Raises typed errors. Never returns raw HTTP responses to callers."""

    async def create_issue(
        self, base_url: str, credentials: dict, payload: dict
    ) -> JiraIssueRef:
        """Returns JiraIssueRef(key, url). Raises JiraApiError subclass on failure."""

    async def get_issue_status(
        self, base_url: str, credentials: dict, issue_key: str
    ) -> JiraIssueStatus:
        """Returns JiraIssueStatus(key, status_category_key, status_name). Raises on failure."""
```

### JiraApiError hierarchy

```python
class JiraApiError(Exception): ...
class JiraAuthError(JiraApiError): ...         # 401
class JiraPermissionError(JiraApiError): ...   # 403
class JiraNotFoundError(JiraApiError): ...     # 404
class JiraRateLimitError(JiraApiError):        # 429
    retry_after: int | None
class JiraServerError(JiraApiError): ...       # 5xx
class JiraTimeoutError(JiraApiError): ...      # httpx.TimeoutException
```

`JiraErrorClassifier.classify(response) -> JiraApiError` is a pure function: takes an httpx Response, returns the appropriate error type. One place to maintain the mapping.

---

## 6. Error Handling Matrix

| HTTP Status | Retry | jira_config effect | export status | error_code |
|---|---|---|---|---|
| 201 Created | n/a | reset consecutive_failures=0 | success | — |
| 401 Unauthorized | No | +1 consecutive_failures | failed | JIRA_AUTH_FAILURE |
| 403 Forbidden | No | +1 consecutive_failures | failed | JIRA_PERMISSION_DENIED |
| 404 Not Found (create) | No | no change | failed | JIRA_PROJECT_NOT_FOUND |
| 404 Not Found (sync) | No | no change | (sync) jira_status=not_found | JIRA_ISSUE_DELETED |
| 429 Rate Limited | Yes (3x, backoff) | no change | failed after retries | JIRA_RATE_LIMITED |
| 5xx Server Error | Yes (3x, backoff) | +1 per attempt | failed after retries | JIRA_SERVER_ERROR |
| Timeout | Yes (3x, backoff) | +1 per attempt | failed after retries | JIRA_TIMEOUT |

**consecutive_failures >= 3** → `jira_config.state = 'error'` + SSE degradation alert (EP-10 pattern reused).

**Retry backoff** (export task): 60s, 120s, 240s. Celery `max_retries=3`, `default_retry_delay=60`, exponential via `countdown=60 * (2 ** self.request.retries)`.

For 429: use `Retry-After` header value as `countdown` if present, else fall back to standard backoff.

---

## 7. Idempotency

Two layers:

**Layer 1 — Pre-dispatch check (synchronous, in ExportService)**:
Query `integration_exports` for `work_item_id` with `status IN ('pending', 'retrying')`. If found, return 409. This prevents duplicate Celery tasks from being dispatched.

**Layer 2 — Pre-Jira-call check (in ExportTask)**:
Before calling Jira, reload the `integration_exports` record. If `jira_issue_key` is already set, the Jira call already succeeded (possibly on a previous task execution that crashed before marking success). Skip the API call, mark as success.

This makes the task safe for Celery's at-least-once delivery without creating duplicate Jira issues.

---

## 8. Divergence Detection

Computed at read time — no background job needed:

```python
@property
def is_diverged(work_item: WorkItem, latest_export: IntegrationExport | None) -> bool:
    if latest_export is None:
        return False
    if latest_export.status != 'success':
        return False
    return work_item.current_version_id != latest_export.version_id
```

The API returns `diverged: bool` and `last_export_version_id` on `GET /work-items/:id`. Frontend renders the indicator. No polling, no materialized flag — current_version_id is available in the work_item row (EP-04).

---

## 9. API Endpoints

```
POST   /api/v1/work-items/:id/export
       Body: {}  (no payload — export reads from current state)
       Auth: authenticated member with access to work item
       Returns: 202 { export_id, status: "pending" }
       Errors: 422 ELEMENT_NOT_READY | JIRA_CONFIG_NOT_FOUND | JIRA_CONFIG_DEGRADED
                    JIRA_PROJECT_MAPPING_NOT_FOUND
               409 EXPORT_ALREADY_IN_PROGRESS

GET    /api/v1/work-items/:id/exports
       Auth: authenticated member with access to work item
       Returns: 200 { exports: [...], diverged: bool }
       Each export: { id, jira_issue_key, jira_issue_url, status, exported_at,
                      exported_by, jira_status, jira_status_last_synced_at,
                      version_id, is_current_version, error_code, attempt_count }

POST   /api/v1/exports/:id/retry
       Auth: requires RETRY_EXPORTS capability
       Returns: 202 { export_id, status: "retrying" }
       Errors: 404 if export not found
               422 if export status is not 'failed'
               403 if no RETRY_EXPORTS capability
```

Note: retry reuses the existing snapshot_data — it does NOT rebuild the snapshot. The snapshot is what was sent (or attempted) the first time. Rebuilding on retry would create a different payload, violating idempotency guarantees.

---

## 10. Celery Task Configuration

### export_task

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    name="tasks.export_task",
    acks_late=True,          # re-queue on worker crash
    reject_on_worker_lost=True,
    soft_time_limit=45,      # Fixed per backend_review.md CA-3: guard against hung Jira connections
                             # SoftTimeLimitExceeded is raised, caught, task marks failed and does NOT retry
)
def export_task(self, export_id: str): ...
```

`acks_late=True` ensures the task is re-queued if the worker crashes mid-execution. Combined with the Layer 2 idempotency check, this is safe.

### sync_task (periodic)

```python
@celery_app.task(name="tasks.sync_jira_statuses")
def sync_jira_statuses(): ...

# Beat schedule
CELERYBEAT_SCHEDULE = {
    "sync-jira-statuses": {
        "task": "tasks.sync_jira_statuses",
        "schedule": crontab(minute="*/15"),
    }
}
```

Sync task processes in a paginated loop (Fixed per backend_review.md CA-5): fetch batches of 100 records in a loop until no records remain or a configurable `max_items_per_run` (default: 1000) is reached. A single-batch fetch is unbounded and will OOM on large datasets. Skips configs in error state. Does not raise on individual issue failure — logs and continues.

---

## 11. JiraFieldMapper

Maps `WorkItemSnapshot` → Jira issue fields dict. The mapping is driven by `element_type_mappings` JSONB stored in `jira_project_mappings` (EP-10 schema):

```python
class JiraFieldMapper:
    def map(self, snapshot: WorkItemSnapshot, mapping: JiraProjectMapping) -> dict:
        issue_type_id = mapping.element_type_mappings.get(snapshot.element_type)
        fields = {
            "project": {"key": mapping.jira_project_key},
            "issuetype": {"id": issue_type_id},
            "summary": snapshot.title,
            "description": self._build_adf(snapshot),
        }
        if snapshot.assignee and mapping.assignee_account_id_map:
            jira_account_id = mapping.assignee_account_id_map.get(str(snapshot.assignee.id))
            if jira_account_id:
                fields["assignee"] = {"accountId": jira_account_id}
        return fields

    def _build_adf(self, snapshot: WorkItemSnapshot) -> dict:
        """Converts sections + override note to Atlassian Document Format."""
        ...
```

ADF conversion is isolated here. If Jira's API ever supports Markdown directly, this is the only place to change.

---

## 12. Decisions and Tradeoffs

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Export execution | Async Celery task | Synchronous in request | Jira can be slow/unavailable; 10s+ response times in a synchronous handler is unacceptable |
| Re-export behavior | New Jira issue | Update existing issue | No write-back is the explicit contract; updating post-export content in Jira risks overwriting Jira-side changes ⚠️ originally MVP-scoped — see decisions_pending.md |
| Snapshot rebuild on retry | Reuse original snapshot | Rebuild from current state | Retry must send the same payload; rebuilding changes the semantics from "retry" to "new export" |
| Divergence detection | Computed at read time | Materialized flag on work_item | Avoids write amplification; version_id comparison is O(1) |
| Sync mechanism | Celery periodic polling | Webhooks | Webhooks require public endpoint, ingress config, and Jira-side setup — not worth it at current scale ⚠️ originally MVP-scoped — see decisions_pending.md |
| Status mapping basis | statusCategory.key | status name string | Status names are user-configurable in Jira; category keys are stable across instances |
| Idempotency | Two-layer (pre-dispatch + pre-call) | Single layer | Celery at-least-once delivery requires the adapter-level check; pre-dispatch is UX only |

---

## 13. Out of Scope

> ⚠️ Items below were originally MVP-scoped deferrals. Review each against full-product scope; log outcomes in decisions_pending.md.

- Webhook-based Jira status callbacks
- Bulk export UI
- Two-way sync (Jira changes reflected in platform content)
- Custom field mapping configuration UI (mapping is set via project mappings API in EP-10)
- Jira issue transitions triggered from the platform
- Export scheduling or automation of any kind
- Project-scoped Jira configs (workspace-level only, schema already supports it)
