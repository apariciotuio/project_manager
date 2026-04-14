# EP-16 Admin Spec — US-165

## US-165: Admin Storage Dashboard and Quota Enforcement

### Storage Usage Dashboard

WHEN a platform admin or workspace admin navigates to the storage admin page
THEN `GET /api/v1/admin/storage/usage` returns a list of workspaces with per-workspace storage statistics
AND each entry includes: `workspace_id`, `workspace_name`, `total_bytes_used`, `file_count`, `quota_bytes`, `quota_utilization_pct`, `quarantined_count`
AND the list is sorted by `total_bytes_used DESC` by default
AND the response supports `?sort_by=quota_utilization|total_bytes|file_count&order=asc|desc`
AND the response supports cursor-based pagination (`?limit=50&after=<cursor>`)

WHEN called by a non-admin user
THEN the server returns 403

WHEN called by a workspace admin (not platform admin)
THEN the response is scoped to their workspace only (single-item list)
AND the `quota_bytes` field reflects the workspace-level configured quota

WHEN a workspace has zero attachments
THEN it is included in the list with `total_bytes_used=0` and `file_count=0`

### Per-Workspace Quota Enforcement

WHEN an admin sends `PATCH /api/v1/admin/storage/workspaces/:workspace_id/quota` with `{ quota_bytes: N }`
THEN the server validates `quota_bytes` >= 0 and <= the platform maximum (default: 10GB per workspace, configurable via environment variable)
AND stores the quota override in the `workspace_storage_configs` table (or equivalent EP-10 config pattern)
AND returns 200 with the updated quota configuration
AND subsequent upload requests for that workspace use the new quota immediately (no cache invalidation needed — quota is checked at request time)

WHEN `quota_bytes` is set to 0
THEN all new upload requests for the workspace are rejected with `ATTACHMENT_QUOTA_EXCEEDED`
AND existing attachments are unaffected

WHEN `quota_bytes` is not provided in the PATCH body
THEN the server returns 422

WHEN a workspace has no custom quota set
THEN the default quota (100MB per work item, configurable globally) applies
AND workspace-level total cap defaults to the platform default (no override)

### Admin Override Delete

WHEN an admin sends `DELETE /api/v1/admin/attachments/:id` 
THEN the server soft-deletes the attachment regardless of the `uploaded_by` field
AND writes an audit event with `actor_id=admin_user_id`, `action='admin_delete'`, `attachment_id`, `workspace_id`, `reason` (from optional `?reason=` query param)
AND returns 204

WHEN the attachment does not exist or is already soft-deleted
THEN the server returns 404

WHEN `DELETE /api/v1/admin/attachments/:id` is called by a non-admin
THEN the server returns 403

### Cleanup Job Status

WHEN `GET /api/v1/admin/storage/cleanup-status` is called by an admin
THEN the server returns the result of the last `cleanup_soft_deleted` Celery beat job run
AND the response includes: `last_run_at`, `status` (success|failure|running), `attachments_purged`, `bytes_freed`, `s3_objects_deleted`, `errors_count`
AND if the job has never run, `last_run_at` is null and `status` is `never_run`

WHEN the cleanup job is currently running
THEN `status` is `running` and `attachments_purged` reflects the count so far (best-effort, updated per batch)

WHEN the cleanup job failed in its last run
THEN `status` is `failure`, `errors_count` > 0, and `error_detail` contains the last exception message (truncated to 500 chars)
AND an admin alert was sent at job failure time (same notification channel as quarantine alerts)

### Cleanup Job Behaviour

WHEN the `cleanup_soft_deleted` Celery beat task runs (daily at 02:00 UTC)
THEN it queries all `attachments` where `soft_deleted_at IS NOT NULL AND soft_deleted_at < now() - interval '30 days'`
AND for each such attachment: deletes the S3 object at `storage_key`
AND if `thumbnail_key` is NOT NULL: deletes the S3 object at `thumbnail_key`
AND hard-deletes the attachment DB record
AND processes in batches of 100 to avoid memory pressure
AND logs `attachments_purged`, `bytes_freed` at INFO level (not the storage keys — those must not be logged)

WHEN an S3 delete call fails for an individual attachment
THEN the job logs the error at WARNING level and continues to the next record (partial failure is acceptable)
AND the failed attachment is retried in the next daily run (its `soft_deleted_at` still qualifies)
AND the job's final status records `errors_count` for admin visibility

WHEN there are quarantined attachments with `soft_deleted_at IS NULL`
THEN they are NOT processed by the regular cleanup job
AND they remain until an admin explicitly purges them via the admin purge endpoint
