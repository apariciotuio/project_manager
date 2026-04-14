# Spec: Admin — Puppet Configuration + Documentation Sources
## US-135 (Admin: Configure Puppet Integration and Documentation Sources)

**Epic**: EP-13
**Date**: 2026-04-13
**Status**: Draft

---

## Scope

Admin members with `CONFIGURE_INTEGRATION` capability manage Puppet credentials and documentation source registrations. Puppet config reuses the `integration_configs` table from EP-10 (`provider='puppet'`). Documentation sources are stored in the new `documentation_sources` table. Health check and reindex are admin-triggered Celery tasks.

---

## US-135: Admin Configuration

### AC-135-1: Admin can create a Puppet integration config

WHEN an admin sends `POST /api/v1/admin/integrations/puppet`
  with `{ "base_url": "https://puppet.internal/", "api_key": "...", "workspace_id": "uuid" }`
THEN an `integration_configs` record is created with `provider='puppet'`, `state='active'`
AND the `api_key` is encrypted via Fernet and stored in `credentials_ref` (never plaintext)
AND a `POST /api/v1/admin/puppet/health-check` is automatically triggered to validate the connection
AND the admin actor is recorded in `audit_events` with `action='puppet_config_created'`

### AC-135-2: Credentials are never returned in GET responses

WHEN an admin fetches `GET /api/v1/admin/integrations/puppet`
THEN the response includes config metadata but NOT the `api_key` or any decrypted credentials
AND the response includes `{ "id", "base_url", "state", "last_health_check_status", "last_health_check_at", "created_at" }`

### AC-135-3: Admin can update Puppet config credentials

WHEN an admin sends `PATCH /api/v1/admin/integrations/puppet/{id}` with a new `api_key`
THEN the old credentials are rotated (write new, delete old — `CredentialsStore.rotate`)
AND `audit_events` records `action='puppet_config_updated'` with `before_value` and `after_value` (excluding credentials)

### AC-135-4: Health check validates Puppet connectivity

WHEN `POST /api/v1/admin/puppet/{id}/health-check` is called
THEN a Celery task `puppet.health_check` is enqueued
AND the task calls the Puppet probe endpoint with stored credentials
AND on success: `integration_configs.state='active'`, `last_health_check_status='ok'`, `last_health_check_at=now()`
AND on failure: `integration_configs.state='error'`, `last_health_check_status='error'`, error message stored
AND the HTTP response is `202 Accepted` with `{ "task_id": "..." }` (async)

### AC-135-5: Admin can disable the Puppet integration

WHEN an admin sends `PATCH /api/v1/admin/integrations/puppet/{id}` with `{ "state": "disabled" }`
THEN `integration_configs.state='disabled'`
AND all subsequent indexing tasks for this workspace are no-ops until re-enabled
AND audit event recorded with `action='puppet_config_disabled'`

### AC-135-6: Admin can add a documentation source

WHEN an admin sends `POST /api/v1/admin/documentation-sources`
  with `{ "workspace_id": "uuid", "source_type": "github_repo|url|path", "url": "string", "name": "string", "is_public": boolean }`
THEN a `documentation_sources` record is created with `status='pending'`
AND a Celery task `puppet.index_doc_source` is enqueued to trigger initial indexing
AND audit event recorded with `action='doc_source_added'`

### AC-135-7: Documentation source types are validated

WHEN a source is created with `source_type='github_repo'`
THEN `url` must match `https://github.com/{owner}/{repo}` pattern
WHEN `source_type='url'`
THEN `url` must be a valid HTTPS URL
WHEN neither matches
THEN the response is `400 Bad Request` with `"code": "INVALID_SOURCE_TYPE"`

### AC-135-8: Admin can list documentation sources

WHEN an admin sends `GET /api/v1/admin/documentation-sources?workspace_id={id}`
THEN the response lists all sources for the workspace
AND each source includes `{ "id", "name", "source_type", "url", "is_public", "status", "last_indexed_at", "item_count" }`
AND `status` is one of `pending | indexing | indexed | error`

### AC-135-9: Admin can delete a documentation source

WHEN an admin sends `DELETE /api/v1/admin/documentation-sources/{id}`
THEN the source record is soft-deleted (`deleted_at` timestamp set)
AND a Celery task `puppet.deindex_doc_source` is enqueued to remove the source's docs from Puppet
AND audit event recorded with `action='doc_source_removed'`

### AC-135-10: Admin can trigger a full reindex

WHEN an admin sends `POST /api/v1/admin/puppet/reindex` with `{ "workspace_id": "uuid" }`
THEN a Celery task `puppet.full_reindex` is enqueued for the workspace
AND the task re-queues `puppet.index_work_item` for all non-archived work items in the workspace
AND the HTTP response is `202 Accepted` with `{ "task_id": "...", "item_count": N }`
AND a reindex can only be triggered once per 10 minutes per workspace (rate-limited, returns 429 if exceeded)
AND audit event recorded with `action='puppet_reindex_triggered'`

### AC-135-11: Capability check is enforced on all admin endpoints

WHEN any Puppet admin endpoint is called by a user without `CONFIGURE_INTEGRATION` capability
THEN the response is `403 Forbidden` with `"code": "CAPABILITY_REQUIRED"`

---

## API Contracts

```
POST   /api/v1/admin/integrations/puppet
GET    /api/v1/admin/integrations/puppet
PATCH  /api/v1/admin/integrations/puppet/{id}
POST   /api/v1/admin/puppet/{id}/health-check    → 202 Accepted
POST   /api/v1/admin/puppet/reindex              → 202 Accepted

POST   /api/v1/admin/documentation-sources
GET    /api/v1/admin/documentation-sources?workspace_id={id}
DELETE /api/v1/admin/documentation-sources/{id}

All require: Authorization: Bearer <token>
All require: CONFIGURE_INTEGRATION capability
```

---

## Table: documentation_sources

```sql
CREATE TABLE documentation_sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id),
    name            varchar(255) NOT NULL,
    source_type     varchar(50) NOT NULL CHECK (source_type IN ('github_repo', 'url', 'path')),
    url             text NOT NULL,
    is_public       boolean NOT NULL DEFAULT false,
    status          varchar(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'indexing', 'indexed', 'error')),
    last_indexed_at timestamptz,
    item_count      integer,
    error_message   text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz
);

CREATE INDEX idx_doc_sources_workspace ON documentation_sources(workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_doc_sources_public ON documentation_sources(is_public) WHERE deleted_at IS NULL AND is_public = true;
```

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|------------------|
| Health check called while Puppet is being set up | Returns 202, task runs async, result visible via GET status |
| Reindex triggered while previous reindex is running | Returns 429 with `"message": "Reindex already in progress or rate limit reached"` |
| Doc source URL is unreachable during indexing | Task retries 3x, then sets `status='error'`, `error_message` populated |
| Admin deletes Puppet config while reindex is in progress | Running tasks see no config, become no-ops; Celery beat stops scheduling future tasks |
| Two admins configure Puppet simultaneously | Second POST should return 409 Conflict if one already exists (unique constraint on workspace_id + provider) |
