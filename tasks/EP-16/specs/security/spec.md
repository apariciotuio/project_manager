# EP-16 Security Spec — US-164, US-166

> **Resolved 2026-04-14 (decisions_pending.md #29)**: VPN-internal deployment. Signed URLs, ClamAV scanning, scan-status machine, and IAM session-tag revocation are dropped. Authenticated streaming endpoints with JWT + workspace membership + capability checks replace them.

## US-164: Delete Authorization (Uploader or Workspace Admin)

### Delete Own Attachment

WHEN a user sends `DELETE /api/v1/attachments/:id`
THEN the server checks that the requesting user is the `uploaded_by` user on the attachment
OR the requesting user has the Workspace Admin profile in the attachment's `workspace_id`
AND if authorized, sets `soft_deleted_at = now()` on the attachment record
AND returns 204 No Content.

WHEN the requesting user is neither the uploader nor a Workspace Admin
THEN the server returns 403 with `{ error: { code: "ATTACHMENT_DELETE_FORBIDDEN" } }`
AND the attachment is NOT modified.

WHEN the attachment does not exist or is already soft-deleted
THEN the server returns 404.

WHEN the attachment belongs to a different workspace than the requesting user's active workspace
THEN the server returns 404 (not 403 — do not leak existence of cross-workspace resources).

### Post-Deletion Behaviour

WHEN an attachment is soft-deleted
THEN it is excluded from all `GET /api/v1/work-items/:id/attachments` responses immediately
AND `GET /api/v1/attachments/:id` returns 404 immediately
AND the object in storage is NOT deleted immediately — deletion is deferred to the Celery cleanup job
AND the timeline event `attachment_deleted` is written to `timeline_events` with `actor_id` and `occurred_at`.

WHEN a work item is hard-deleted (cascade)
THEN all child `attachments` records are also soft-deleted via application cascade
AND the cleanup job handles the object-storage cleanup within 30 days.

---

## US-166: Authenticated Streaming + Upload Controls

### Authenticated Download Endpoint

WHEN `GET /api/v1/attachments/:id/download` is called
THEN the server authenticates the JWT.
AND verifies the caller is an active member of the attachment's workspace.
AND verifies the caller has the `can_view_attachment` capability.
AND if any check fails, the server returns 401 (no JWT) or 403 (other failures).

WHEN all checks pass
THEN the server streams the object body through the response with `Content-Type`, `Content-Disposition`, `ETag` headers.
AND no presigned URL is ever issued.
AND the storage key is never exposed to the client.
AND an audit event `attachment.downloaded` is written with `actor_id`, `attachment_id`, `occurred_at`.

### Upload Validation

WHEN a user POSTs a new attachment
THEN the server validates the declared `Content-Type` against an allowlist (`image/png`, `image/jpeg`, `image/gif`, `image/webp`, `application/pdf`, plus workspace-configured additions).
AND validates size ≤ `per_file_max_bytes` from `workspace_storage_configs` (default 10 MB).
AND validates total workspace usage ≤ `quota_bytes`.
AND audits `attachment.uploaded` with `actor_id`, `attachment_id`, `size_bytes`.

WHEN a declared content-type is not in the allowlist
THEN the server returns 422 `ATTACHMENT_TYPE_REJECTED`.

WHEN size or quota is exceeded
THEN the server returns 422 `ATTACHMENT_TOO_LARGE` / `WORKSPACE_QUOTA_EXCEEDED`.

### Rate Limits

WHEN a user exceeds 20 uploads within a sliding 1-hour window
THEN the server returns 429.

WHEN the same IP exceeds 100 attachment-endpoint requests in 1 minute
THEN the IP rate limiter from EP-12 returns 429 regardless of user-level state.

### Image Inline in Comments

WHEN a user pastes or drags an image into a comment editor
THEN the client uploads it via `POST /api/v1/comments/:id/attachments`.
AND the server applies the same validation + audit as any other upload.
AND the resulting attachment is rendered inline in the comment via `GET /api/v1/attachments/:id/download` (same authenticated streaming endpoint).
