# EP-16 Security Spec — US-164, US-166

## US-164: Delete Authorization (Uploader or Workspace Owner)

### Delete Own Attachment

WHEN a user sends `DELETE /api/v1/attachments/:id`
THEN the server checks that the requesting user is the `uploaded_by` user on the attachment
OR the requesting user has the `owner` or `admin` role in the attachment's `workspace_id`
AND if authorized, sets `soft_deleted_at = now()` on the attachment record
AND returns 204 No Content

WHEN the requesting user is neither the uploader nor a workspace owner/admin
THEN the server returns 403 with `{ error: { code: "ATTACHMENT_DELETE_FORBIDDEN" } }`
AND the attachment is NOT modified

WHEN the attachment does not exist or is already soft-deleted
THEN the server returns 404

WHEN the attachment belongs to a different workspace than the requesting user's active workspace
THEN the server returns 404 (not 403 — do not leak existence of cross-workspace resources)

### Post-Deletion Behaviour

WHEN an attachment is soft-deleted
THEN it is excluded from all `GET /api/v1/work-items/:id/attachments` responses immediately
AND `GET /api/v1/attachments/:id` returns 404 immediately
AND the S3 object is NOT deleted immediately — deletion is deferred to the Celery cleanup job
AND the timeline event `attachment_deleted` is written to `timeline_events` with `actor_id` and `occurred_at`

WHEN a work item is hard-deleted (cascade)
THEN all child `attachments` records are also soft-deleted via a DB trigger or application cascade
AND the cleanup job handles the S3 cleanup within 30 days

---

## US-166: Signed URL Expiration and Virus Scan

### Signed URL Security

WHEN `GET /api/v1/attachments/:id` is called by an authenticated workspace member
THEN the server generates a presigned S3 GET URL valid for exactly 15 minutes
AND the URL includes S3 policy conditions scoped to the object key (no wildcard prefix)
AND the URL is NOT stored in any application log, database column, or audit record
AND the response includes `{ url, expires_at }` so the client knows when to refresh

WHEN the same `GET /api/v1/attachments/:id` is called again after the URL expires
THEN a new presigned URL is generated (the server is stateless with respect to signed URL issuance)
AND the old URL has been invalidated by S3 TTL — no server-side revocation needed

WHEN a presigned URL is used after its expiry
THEN S3 returns 403 to the caller directly — the backend is not involved

WHEN a presigned URL is used by a client that is no longer a workspace member (membership revoked mid-session)
THEN the backend cannot retroactively invalidate an issued URL before its 15-minute TTL
AND this is an accepted residual risk, mitigated by the short TTL
AND post-MVP option: S3 bucket policy conditions tied to IAM session tags can reduce this window

### Virus Scan — Pending State

WHEN an attachment is confirmed via `POST /api/v1/attachments/:id/confirm`
THEN `scan_status` is `pending` and the attachment is NOT accessible for download or inline rendering
AND `GET /api/v1/attachments/:id` returns `{ scan_status: "pending" }` with no `url` field
AND any attempt to retrieve the download URL returns 422 with `{ error: { code: "ATTACHMENT_NOT_AVAILABLE" } }`

WHEN the `scan_attachment` Celery task runs
THEN it downloads the attachment from S3 to a temporary directory on the worker
AND passes the file path to `clamd` via the `clamd` Python client (unix socket or TCP)
AND if clamd returns `OK`: sets `scan_status='clean'`, publishes a notification to the work item channel
AND if clamd returns a virus name: sets `scan_status='quarantined'`, does NOT delete the S3 object yet (preserve for forensics)
AND deletes the local temporary file regardless of outcome
AND if clamd is unreachable: raises a retriable Celery exception (max 3 retries, exponential backoff 60s/120s/240s)

WHEN scan_status transitions to `clean`
THEN `GET /api/v1/attachments/:id` now returns a presigned URL as normal
AND if the attachment is inline in a comment, the frontend polling loop (5s interval) detects the status change and renders the image

WHEN scan_status transitions to `quarantined`
THEN the attachment remains permanently inaccessible to all non-admin users
AND an admin notification is sent (workspace admin email or in-app alert, configurable via EP-10)
AND the attachment record is retained in DB with `scan_status='quarantined'` for audit purposes
AND the S3 object is tagged `quarantined=true` for the cleanup job to handle separately (not auto-deleted)

### Quarantine Handling

WHEN an admin views quarantined attachments (via admin storage dashboard)
THEN quarantined attachments are listed separately with the scan result detail
AND an admin can hard-delete a quarantined attachment immediately via `DELETE /api/v1/admin/attachments/:id/purge`

WHEN `DELETE /api/v1/admin/attachments/:id/purge` is called by a non-admin
THEN the server returns 403

WHEN the purge endpoint is called by an admin
THEN the attachment record is hard-deleted from the DB
AND the S3 object is immediately deleted
AND an audit event is written with `actor_id`, `attachment_id`, `reason='admin_purge'`

### Rate Limits

WHEN a user sends more than 20 `POST /api/v1/work-items/:id/attachments/request-upload` requests within a sliding 1-hour window
THEN the server returns 429
AND the Redis key `rate:upload:{user_id}` is decremented on the next window reset

WHEN the same IP sends more than 100 requests to any attachment endpoint within 1 minute
THEN the IP-level rate limiter (from EP-12 middleware) applies
AND returns 429 independent of the user-level limit
