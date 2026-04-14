# EP-16 Backend Tasks

> **Scope (2026-04-14, decisions_pending.md #29)**: VPN-internal deployment. **Dropped**: ClamAV, `attachment_scan_status` state machine, Celery scan queue, signed URLs (presigned PUT/GET), SSE scan-status push, IAM session-tag revocation, 5s scan-status polling. **Kept**: PDF thumbnail generation (pdf2image + Pillow, Celery), authenticated streaming download endpoint, content-type validation, file size limits per user/workspace, upload rate limits, audit of uploads/downloads, inline images in comments (paste/drag). Below is rewritten — obsolete groups removed, not flagged.

---

## Group 0: Migrations

- [ ] **B0.1** Write Alembic migration: create `attachments` table with columns `id`, `workspace_id`, `work_item_id` (nullable), `comment_id` (nullable), `uploaded_by`, `filename`, `mime_type`, `size_bytes`, `storage_key`, `thumbnail_key` (nullable), `soft_deleted_at` (nullable), `created_at`. No `scan_status` column (decision #29). CHECK constraint: at least one of `work_item_id` / `comment_id` is set.
  - Indexes: `idx_attachments_work_item (work_item_id) WHERE soft_deleted_at IS NULL`, `idx_attachments_comment (comment_id) WHERE soft_deleted_at IS NULL`, `idx_attachments_cleanup (soft_deleted_at) WHERE soft_deleted_at IS NOT NULL`, `idx_attachments_workspace_usage (workspace_id)` (for usage aggregation)
  - AC: migration up/down is idempotent
- [ ] **B0.2** Write Alembic migration: create `workspace_storage_configs` table (workspace_id PK, quota_bytes, per_user_quota_bytes, updated_at) with defaults from config when row absent
- [ ] **B0.3** Write Alembic migration: create `storage_cleanup_runs` table (last_run_at, status, attachments_purged, bytes_freed, s3_objects_deleted, errors_count, error_detail)
- [ ] Do NOT create `attachment_scan_status`, `attachment_scans`, any ClamAV-related column/table (decision #29)

---

## Group 1: StorageAdapter

- [ ] **B1.1** [RED] Write tests for `FakeStorageAdapter`: `object_exists`, `get_object_size`, `delete_object`, `stream_object(key) -> AsyncIterator[bytes]`, `upload_from_bytes(key, data, content_type)`, `upload_from_file(key, file, content_type)`
  - AC: all methods work in-memory; no network calls; tests fully isolated
  - No `generate_presigned_put` / `generate_presigned_get` methods (decision #29)
- [ ] **B1.2** [GREEN] Implement `FakeStorageAdapter` in `tests/fakes/fake_storage_adapter.py` implementing `IStorageAdapter`
- [ ] **B1.3** [RED] Write contract tests for `IStorageAdapter` that run against both `FakeStorageAdapter` and (with env flag) `S3Adapter`
  - AC: same test suite passes on both; S3Adapter tests skipped if `S3_INTEGRATION_TESTS=false`
- [ ] **B1.4** [GREEN] Implement `IStorageAdapter` port in `domain/ports/storage_adapter.py` — methods: `upload_from_file`, `upload_from_bytes`, `stream_object`, `object_exists`, `get_object_size`, `delete_object`
- [ ] **B1.5** [GREEN] Implement `S3Adapter` in `infrastructure/adapters/s3_adapter.py`
  - AC: object keys follow `workspaces/{workspace_id}/attachments/{attachment_id}/{safe_filename}` pattern; no object keys logged at INFO or above
- [ ] **B1.6** [REFACTOR] Extract `sanitize_filename(filename: str) -> str` helper; test edge cases (path traversal `../../../etc/passwd`, unicode, null bytes, very long names)
  - AC: all special characters replaced; UUID prefix makes traversal impossible regardless

---

## Group 2: Domain Model + Repository

- [ ] **B2.1** [RED] Write tests for `Attachment` domain entity: instantiation, `can_view(user, workspace_membership)` (workspace match + `can_view_attachment` capability), `can_delete(user, workspace_role)`, `soft_delete()`
  - AC: triangulate — uploader can delete, workspace admin can delete, stranger cannot; no `scan_status` accessor
- [ ] **B2.2** [GREEN] Implement `Attachment` entity in `domain/models/attachment.py` (no scan-state machine)
- [ ] **B2.3** [RED] Write tests for `IAttachmentRepository` (using FakeAttachmentRepository): `create`, `get_by_id`, `list_by_work_item`, `list_by_comment`, `update_thumbnail_key`, `soft_delete`, `list_soft_deleted_older_than`
  - AC: workspace isolation — `list_by_work_item` must not return attachments from other workspaces
  - Removed: `update_scan_status`, `list_pending_scan`
- [ ] **B2.4** [GREEN] Implement `FakeAttachmentRepository` in `tests/fakes/`
- [ ] **B2.5** [GREEN] Implement SQLAlchemy `AttachmentRepository` in `infrastructure/persistence/attachment_repository.py`
  - AC: all queries include `workspace_id` filter; no raw SQL; uses async session

---

## Group 3: AttachmentService

- [ ] **B3.1** [RED] Write tests for `AttachmentService.upload`:
  - Valid multipart upload → creates attachment record, streams body to object storage, enqueues thumbnail task if applicable (image or PDF), returns attachment metadata
  - Disallowed MIME type → raises `AttachmentTypeRejectedError`
  - File too large → raises `AttachmentTooLargeError`
  - Work item / per-user / workspace quota exceeded → raises appropriate quota error
  - Rate limit exceeded → raises `RateLimitExceededError`
  - Work item not in user's workspace → raises `NotFoundError`
  - Caller lacks `upload_attachment` capability → raises `ForbiddenError`
  - AC: uses FakeStorageAdapter and FakeAttachmentRepository; no S3 calls
  - Note: single-phase upload (no `request-upload` + `confirm`); direct multipart to our BE which streams to S3. Decision #29 removed presigned PUT.
- [ ] **B3.2** [RED] Write tests for `AttachmentService.download_stream`:
  - Caller in same workspace + has `can_view_attachment` → returns async iterator of bytes + content-type + content-disposition header values
  - Cross-workspace → raises `NotFoundError` (never 403 — don't leak existence)
  - Soft-deleted → raises `NotFoundError`
  - Caller lacks capability → raises `ForbiddenError`
- [ ] **B3.3** [RED] Write tests for `AttachmentService.delete`:
  - Uploader deletes own attachment → soft-deleted
  - Workspace admin deletes → soft-deleted
  - Stranger attempts delete → raises `ForbiddenError`
  - Cross-workspace → raises `NotFoundError`
- [ ] **B3.4** [GREEN] Implement `AttachmentService` in `application/services/attachment_service.py`
  - AC: constructor-injected `IStorageAdapter`, `IAttachmentRepository`, `IRateLimiter`, `IWorkItemRepository`, `ICeleryClient`; no direct DB or boto3 calls
- [ ] **B3.5** [REFACTOR] Extract quota-check logic into `AttachmentQuotaChecker` (per-user + per-workspace)
- [ ] **B3.6** [RED] Write tests for `AdminAttachmentService.admin_delete` and `purge_soft_deleted`
  - AC: admin can delete any workspace's attachment; purge hard-deletes DB record + object storage; audit event written
- [ ] **B3.7** [GREEN] Implement `AdminAttachmentService` in `application/services/admin_attachment_service.py`

---

## Group 4: Upload & Download Endpoints

- [ ] **B4.1** [RED] Write integration tests for `POST /api/v1/work-items/:id/attachments` (multipart)
  - Valid → 201 with full attachment metadata (`{ attachment_id, filename, mime_type, size_bytes, thumbnail_url?, download_url }`)
  - Invalid MIME → 422 `ATTACHMENT_TYPE_REJECTED` (content-type sniffed via `python-magic`; server rejects spoofed headers)
  - Too large → 413 `ATTACHMENT_TOO_LARGE`
  - Quota exceeded → 422 `ATTACHMENT_QUOTA_EXCEEDED`
  - Rate limited → 429
  - Unauthenticated → 401
  - Wrong workspace / no capability → 404 (don't leak existence)
- [ ] **B4.2** [RED] Write integration tests for `GET /api/v1/attachments/:id` (metadata)
  - Accessible → 200 with `{ attachment_id, filename, mime_type, size_bytes, thumbnail_url?, download_url }`; `download_url` points to `/api/v1/attachments/:id/download` (NOT a presigned URL)
  - Soft-deleted / cross-workspace / missing → 404
- [ ] **B4.3** [RED] Write integration tests for `GET /api/v1/attachments/:id/download` (authenticated streaming)
  - Authorised caller → 200 with `Content-Type`, `Content-Disposition`, `Content-Length`; body is the object bytes streamed through the BE
  - Cross-workspace / missing / soft-deleted → 404
  - Missing JWT → 401
  - Caller lacks `can_view_attachment` capability → 403
  - `Range` header supported (partial content 206) for large files / inline PDF
  - Audit event `attachment.downloaded` written on every successful response
- [ ] **B4.4** [RED] Write integration tests for `GET /api/v1/attachments/:id/thumbnail`
  - Accessible + thumbnail exists → 200 streaming the thumbnail bytes
  - Thumbnail not yet generated → 204 (client falls back to generic icon)
  - Cross-workspace → 404
- [ ] **B4.5** [RED] Write integration tests for `DELETE /api/v1/attachments/:id`
  - Uploader → 204
  - Workspace admin → 204
  - Stranger → 403
  - Not found → 404
- [ ] **B4.6** [RED] Write integration tests for `GET /api/v1/work-items/:id/attachments`
  - Returns list ordered by `created_at DESC`, excluding soft-deleted
  - Pagination: `?limit=20&cursor=<cursor>` with `has_next`
  - Workspace scope enforced
- [ ] **B4.7** [GREEN] Implement `AttachmentController` in `presentation/controllers/attachment_controller.py`
  - AC: no business logic in controller; delegates to `AttachmentService`; handles exception-to-HTTP mapping. Download endpoint returns `StreamingResponse` wrapping `storage_adapter.stream_object(key)`.
- [ ] **B4.8** [GREEN] Register routes in FastAPI router; apply EP-12 auth + rate limit middleware. Do NOT register `POST /attachments/:id/confirm` or any `request-upload` endpoint (decision #29 replaced presigned PUT flow).

---

## Group 5: (removed — no ClamAV scan task per decision #29)

ClamAV, `clamd`, `scan_attachment` Celery task, `attachment_scan_status` enum, quarantine flow, `AdminNotificationService.notify_quarantine` — **all out of scope**. VPN-internal deployment; insider-risk-only threat model.

---

## Group 6: Celery Thumbnail Task (images + PDF — decision #29)

- [ ] **B6.1** [RED] Write tests for `generate_thumbnail` Celery task:
  - PNG/JPEG/WebP input → thumbnail uploaded as JPEG 256x256 bounding box via Pillow; `thumbnail_key` set on record
  - PDF input → first page rendered to PNG via `pdf2image` (poppler), downsampled to 256x256 JPEG, uploaded; `thumbnail_key` set (decision #29 — PDF thumbnails kept)
  - Non-image, non-PDF MIME → task exits without processing
  - Decompression bomb (>50MP) → `DecompressionBombError` caught; attachment marked `thumbnail_status='failed'` (nullable column); no retry
  - Corrupt image → `PIL.UnidentifiedImageError` caught; same handling
  - Corrupt PDF → `pdf2image.exceptions.PDFInfoNotInstalledError` / `PDFPageCountError` caught; same handling
  - AC: uses FakeStorageAdapter; unit test uses tiny embedded PNG/PDF
- [ ] **B6.2** [GREEN] Implement `generate_thumbnail` task in `infrastructure/tasks/generate_thumbnail.py`
  - AC: `PIL.Image.MAX_IMAGE_PIXELS = 50_000_000`; aspect ratio preserved; temp file cleaned in `finally`; poppler binary required in runtime image (document in Dockerfile)

---

## Group 7: Celery Cleanup Task

- [ ] **B7.1** [RED] Write tests for `cleanup_soft_deleted` Celery beat task:
  - Attachments soft-deleted >30 days ago → storage objects deleted, DB records hard-deleted
  - Attachments soft-deleted <30 days ago → untouched
  - Storage delete failure for one attachment → logged, others continue, `errors_count` incremented
  - Job result written to `storage_cleanup_runs`
  - AC: batch size 100; FakeStorageAdapter; FakeAttachmentRepository
- [ ] **B7.2** [GREEN] Implement `cleanup_soft_deleted` task in `infrastructure/tasks/cleanup_soft_deleted.py`
- [ ] **B7.3** [GREEN] Configure Celery beat schedule in `infrastructure/celery_config.py`: daily at 02:00 UTC

---

## Group 8: Admin Quota Endpoints

- [ ] **B8.1** [RED] Write integration tests for `GET /api/v1/admin/storage/usage`
  - Superadmin → full workspace list with stats
  - Workspace admin → scoped to own workspace
  - Non-admin → 403
  - Pagination and sort params
- [ ] **B8.2** [RED] Write integration tests for `PATCH /api/v1/admin/storage/workspaces/:id/quota`
  - Valid quota → 200 with updated config
  - quota_bytes = 0 → subsequent uploads rejected
  - Exceeds platform max → 422
  - Missing quota_bytes → 422
  - Non-admin → 403
- [ ] **B8.3** [RED] Write integration tests for `GET /api/v1/admin/storage/cleanup-status`
  - Never run → `status: "never_run"`
  - After successful run → stats present
  - Non-admin → 403
- [ ] **B8.4** [GREEN] Implement `AdminStorageController` in `presentation/controllers/admin_storage_controller.py`
- [ ] **B8.5** [GREEN] Implement `AdminStorageService` in `application/services/admin_storage_service.py`
  - AC: storage usage query uses `idx_attachments_workspace_usage` index path (verify with EXPLAIN in integration test)

---

## Group 9: Rate Limiting

- [ ] **B9.1** [RED] Write tests for `AttachmentRateLimiter`: sliding window counter in Redis; 20 uploads per hour per user; returns remaining count and reset time
  - AC: uses `FakeRedis` (fakeredis library); no real Redis in unit tests
- [ ] **B9.2** [GREEN] Implement `AttachmentRateLimiter` in `infrastructure/rate_limiting/attachment_rate_limiter.py`
  - AC: uses `ZADD`/`ZREMRANGEBYSCORE`/`ZCARD` pattern (sorted set, score=timestamp); atomic via Lua script or pipeline

---

## Group 10: Security Tests

- [ ] **B10.1** [RED] Cross-workspace attachment access: user from workspace A cannot GET/DELETE/DOWNLOAD attachments from workspace B → 404
- [ ] **B10.2** [RED] MIME type bypass: server-side content-type sniffing (via `python-magic`) rejects even if client sends wrong MIME in multipart headers
- [ ] **B10.3** [RED] Object key / internal path not in logs: assert no `storage_key` or S3 URL appears in any log output during integration test (capture log handler)
- [ ] **B10.4** [RED] Path traversal in filename: `../../../etc/passwd` as filename → sanitized to safe key; no 500
- [ ] **B10.5** [RED] Rate limit enforcement: 21st upload in 1 hour → 429
- [ ] **B10.6** [RED] Download without JWT → 401; with valid JWT but cross-workspace → 404
- [ ] **B10.7** [RED] Download without `can_view_attachment` capability → 403
- [ ] **B10.8** [RED] Admin purge endpoint: non-admin → 403; admin → hard-delete + audit event
- [ ] **B10.9** [GREEN] Fix any failures from above security tests
- [ ] **B10.10** Workspace scoping: grep every attachment-related query for missing `workspace_id` filter
