# Spec: Work Item Indexing to Puppet
## US-132 (Push Work Items to Puppet Index)

**Epic**: EP-13
**Date**: 2026-04-13
**Status**: Draft

---

## Scope

Every work item create/update/delete triggers an async Puppet indexing job via Celery (`integrations` queue). A daily reconcile job detects drift between the DB and Puppet index and corrects it. Indexing is additive — if Puppet is down, the work item mutation succeeds and indexing retries independently.

---

## US-132: Push Work Item Changes to Puppet Index

### AC-132-1: Work item creation triggers index job

WHEN a work item is created
THEN a Celery task `puppet.index_work_item` is enqueued to the `integrations` queue
AND the task payload includes: `{ "work_item_id": uuid, "event": "created", "workspace_id": uuid }`
AND the task is enqueued asynchronously (the HTTP create response does NOT wait for it)
AND if Puppet is not configured for the workspace, the task is a no-op

### AC-132-2: Work item update triggers index job

WHEN a work item's `title`, `description`, `spec_content`, `aggregated_task_text`, `aggregated_comment_text`, `tags`, `state`, or `owner_id` changes
THEN a Celery task `puppet.index_work_item` is enqueued with `"event": "updated"`
AND the task fetches the current full state from DB (not from event payload) before sending to Puppet

### AC-132-3: Work item deletion triggers deindex job

WHEN a work item is deleted (or transitioned to `archived` state, treated as soft-delete)
THEN a Celery task `puppet.deindex_work_item` is enqueued with `"event": "deleted"`
AND upon task execution, the Puppet adapter calls the delete/deindex API for that item's ID
AND if Puppet returns 404 (already absent), the task succeeds silently (idempotent)

### AC-132-4: Index payload includes required fields

WHEN `puppet.index_work_item` executes
THEN the Puppet payload sent includes:
  ```json
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "title": "string",
    "description": "string",
    "spec_content": "string | null",
    "aggregated_sections": "concatenated spec sections text | null",
    "tags": ["string"],
    "owner_id": "uuid | null",
    "state": "string",
    "type": "string",
    "updated_at": "ISO8601"
  }
  ```
AND PII is NOT included (no email addresses, no personal data beyond `owner_id` UUID)

### AC-132-5: Celery task retries on transient failure

WHEN a Puppet API call fails with a transient error (5xx, timeout, network error)
THEN the task retries with exponential backoff: 60s, 120s, 300s (max 3 retries)
AND after 3 failures, the task is moved to a dead-letter queue
AND an error is logged at ERROR level with `work_item_id`, `attempt_count`, and `error_reason`

### AC-132-6: Dead-letter items are observable

WHEN an indexing task exceeds max retries
THEN the `puppet_index_failures` table is updated with `{ work_item_id, workspace_id, last_error, attempt_count, failed_at }`
AND the admin dashboard integration health panel shows the count of unresolved indexing failures

### AC-132-7: Daily reconcile job detects and corrects drift

WHEN the daily Celery beat `puppet.reconcile` job runs (default 02:00 UTC)
THEN it queries all work items with `updated_at > last_reconcile_at` from DB
AND for each, it checks whether Puppet's indexed version `updated_at` matches the DB `updated_at`
AND for items where Puppet is behind (or absent), it enqueues `puppet.index_work_item` with `"event": "reconcile"`
AND for items in Puppet that no longer exist in DB, it enqueues `puppet.deindex_work_item`
AND it records the reconcile run in `puppet_reconcile_runs` table with `{ started_at, completed_at, items_checked, items_reindexed, items_deindexed, errors }`

### AC-132-8: Reconcile job does not index archived items by default

WHEN the reconcile job encounters an archived work item
THEN it does NOT re-index it unless it is already present in Puppet (in which case it deindexes it)

### AC-132-9: Puppet not configured — indexing is a no-op

WHEN no `integration_configs` record with `provider='puppet'` exists for the workspace
THEN all indexing tasks complete immediately with no Puppet calls
AND no errors are logged (expected state for workspaces that haven't configured Puppet)

---

## Event Flow

```
WorkItemService.create()
  └── session.flush()
  └── enqueue puppet.index_work_item(work_item_id, event='created')
      [async, non-blocking]
          └── PuppetAdapter.upsert(payload)
              ├── success → log INFO
              └── failure → retry → dead-letter → log ERROR + update puppet_index_failures
```

---

## Tables Involved

```sql
-- New table for tracking indexing failures
CREATE TABLE puppet_index_failures (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    work_item_id    uuid NOT NULL,
    last_error      text NOT NULL,
    attempt_count   integer NOT NULL DEFAULT 1,
    failed_at       timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz,
    UNIQUE (work_item_id)  -- one live failure record per work item
);

-- New table for reconcile run history
CREATE TABLE puppet_reconcile_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      timestamptz NOT NULL,
    completed_at    timestamptz,
    items_checked   integer NOT NULL DEFAULT 0,
    items_reindexed integer NOT NULL DEFAULT 0,
    items_deindexed integer NOT NULL DEFAULT 0,
    errors          integer NOT NULL DEFAULT 0,
    error_details   jsonb
);
```

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Two rapid updates to same work item | Both tasks enqueued; second wins (Puppet upsert by ID is idempotent) |
| Work item moved between workspaces | Update event re-indexes with new `workspace_id`; old workspace's Puppet filter no longer returns it |
| Puppet returns 429 (rate limit) | Task backs off using Retry-After header if present, else uses exponential backoff |
| Celery worker crashes mid-task | Task requeued by Celery (acks_late=True); upsert is idempotent so re-execution is safe |
| Reconcile job finds 10,000 drifted items | Items batched in groups of 100; tasks enqueued in batches to avoid queue flood |
| Puppet workspace filter drifts from DB | Reconcile corrects it; no permanent drift possible beyond one 24h window |
