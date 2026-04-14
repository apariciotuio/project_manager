# EP-16 Backend Tasks

## Group 0: Migrations

- [ ] **B0.1** Write Alembic migration: create `attachments` table with all columns, CHECK constraint, and indexes (idx_attachments_work_item, idx_attachments_comment, idx_attachments_scan_pending, idx_attachments_cleanup, idx_attachments_workspace_usage)
  - AC: migration up/down is idempotent; `pytest --migrations` passes
- [ ] **B0.2** Write Alembic migration: create `workspace_storage_configs` table with defaults
  - AC: default row is NOT auto-inserted — application uses defaults from config if row absent
- [ ] **B0.3** Write Alembic migration: create `storage_cleanup_runs` table (last_run_at, status, attachments_purged, bytes_freed, s3_objects_deleted, errors_count, error_detail)
  - AC: migration up/down; no data migration required

---

## Group 1: StorageAdapter

- [ ] **B1.1** [RED] Write tests for `FakeStorageAdapter`: `generate_presigned_put`, `generate_presigned_get`, `object_exists`, `get_object_size`, `delete_object`, `download_to_temp`, `upload_from_bytes`
  - AC: all methods work in-memory; no network calls; tests fully isolated
- [ ] **B1.2** [GREEN] Implement `FakeStorageAdapter` in `tests/fakes/fake_storage_adapter.py` implementing `IStorageAdapter`
- [ ] **B1.3** [RED] Write contract tests for `IStorageAdapter` that run against both `FakeStorageAdapter` and (with env flag) `S3Adapter`
  - AC: same test suite passes on both; S3Adapter tests skipped if `S3_INTEGRATION_TESTS=false`
- [ ] **B1.4** [GREEN] Implement `IStorageAdapter` port in `domain/ports/storage_adapter.py`
- [ ] **B1.5** [GREEN] Implement `S3Adapter` in `infrastructure/adapters/s3_adapter.py`
  - AC: object keys follow `workspaces/{workspace_id}/attachments/{attachment_id}/{safe_filename}` pattern; no signed URLs or object keys appear in any log; `ContentLengthRange` condition on PUT presigned URL
- [ ] **B1.6** [REFACTOR] Extract `sanitize_filename(filename: str) -> str` helper; test edge cases (path traversal `../../../etc/passwd`, unicode, null bytes, very long names)
  - AC: all special characters replaced; UUID prefix makes traversal impossible regardless

---

## Group 2: Domain Model + Repository

- [ ] **B2.1** [RED] Write tests for `Attachment` domain entity: instantiation, `is_accessible` (clean only), `can_delete(user_id, workspace_role)`, `mark_confirmed()`, `soft_delete()`
  - AC: triangulate — test uploader can delete, workspace owner can delete, stranger cannot; test pending/quarantined not accessible
- [ ] **B2.2** [GREEN] Implement `Attachment` entity in `domain/models/attachment.py`
- [ ] **B2.3** [RED] Write tests for `IAttachmentRepository` (using FakeAttachmentRepository): `create`, `get_by_id`, `list_by_work_item`, `list_by_comment`, `update_scan_status`, `update_thumbnail_key`, `soft_delete`, `list_pending_scan`, `list_soft_deleted_older_than`
  - AC: workspace isolation — `list_by_work_item` must not return attachments from other workspaces
- [ ] **B2.4** [GREEN] Implement `FakeAttachmentRepository` in `tests/fakes/`
- [ ] **B2.5** [GREEN] Implement SQLAlchemy `AttachmentRepository` in `infrastructure/persistence/attachment_repository.py`
  - AC: all queries include `workspace_id` filter; no raw SQL; uses async session

---

## Group 3: AttachmentService

- [ ] **B3.1** [RED] Write tests for `AttachmentService.request_upload`:
  - Valid request → creates attachment record with `scan_status='pending'`, returns presigned PUT URL + `attachment_id`
  - Disallowed MIME type → raises `AttachmentTypeRejectedError`
  - File too large → raises `AttachmentTooLargeError`
  - Work item quota exceeded → raises `AttachmentQuotaExceededError`
  - Rate limit exceeded → raises `RateLimitExceededError`
  - Work item not in user's workspace → raises `NotFoundError`
  - AC: uses FakeStorageAdapter and FakeAttachmentRepository; no S3 calls
- [ ] **B3.2** [RED] Write tests for `AttachmentService.confirm`:
  - S3 object exists, size matches → enqueues scan + thumbnail tasks, returns attachment
  - S3 object not found → raises `AttachmentUploadNotFoundError`
  - Called by non-uploader → raises `ForbiddenError`
  - Called twice → raises `AlreadyConfirmedError`
- [ ] **B3.3** [RED] Write tests for `AttachmentService.get`:
  - `scan_status='clean'` → returns metadata + fresh presigned GET URL
  - `scan_status='pending'` or `'quarantined'` → returns metadata without URL; `is_accessible=false`
  - Cross-workspace access → raises `NotFoundError`
- [ ] **B3.4** [RED] Write tests for `AttachmentService.delete`:
  - Uploader deletes own attachment → soft-deleted
  - Workspace owner/admin deletes → soft-deleted
  - Stranger attempts delete → raises `ForbiddenError`
  - Cross-workspace → raises `NotFoundError`
- [ ] **B3.5** [GREEN] Implement `AttachmentService` in `application/services/attachment_service.py`
  - AC: constructor-injected `IStorageAdapter`, `IAttachmentRepository`, `IRateLimiter`, `IWorkItemRepository`, `ICeleryClient`; no direct DB or boto3 calls
- [ ] **B3.6** [REFACTOR] Extract quota-check logic into `AttachmentQuotaChecker` (single-responsibility); reuse in admin override path
- [ ] **B3.7** [RED] Write tests for `AdminAttachmentService.admin_delete` and `purge_quarantined`
  - AC: admin can delete any workspace's attachment; purge hard-deletes DB record + S3 object; audit event written
- [ ] **B3.8** [GREEN] Implement `AdminAttachmentService` in `application/services/admin_attachment_service.py`

---

## Group 4: Upload Flow Endpoints

- [ ] **B4.1** [RED] Write integration tests for `POST /api/v1/work-items/:id/attachments/request-upload`
  - Valid → 201 with `{ attachment_id, upload_url, expires_at }`
  - Invalid MIME → 422 `ATTACHMENT_TYPE_REJECTED`
  - Too large → 422 `ATTACHMENT_TOO_LARGE`
  - Quota exceeded → 422 `ATTACHMENT_QUOTA_EXCEEDED`
  - Rate limited → 429
  - Unauthenticated → 401
  - Wrong workspace → 404
- [ ] **B4.2** [RED] Write integration tests for `POST /api/v1/attachments/:id/confirm`
  - Success → 200 `{ attachment_id, scan_status: "pending" }`
  - S3 object missing → 409 `ATTACHMENT_UPLOAD_NOT_FOUND`
  - Wrong user → 403
  - Already confirmed → 409 `ATTACHMENT_ALREADY_CONFIRMED`
- [ ] **B4.3** [RED] Write integration tests for `GET /api/v1/attachments/:id`
  - Clean → 200 with `url` field
  - Pending/quarantined → 200 with no `url` field and `scan_status` set
  - Not found → 404
  - Cross-workspace → 404
- [ ] **B4.4** [RED] Write integration tests for `DELETE /api/v1/attachments/:id`
  - Uploader → 204
  - Workspace owner → 204
  - Stranger → 403
  - Not found → 404
- [ ] **B4.5** [RED] Write integration tests for `GET /api/v1/work-items/:id/attachments`
  - Returns list ordered by `created_at DESC`, excluding soft-deleted
  - Pagination: `?limit=20&after=<cursor>`
  - Workspace scope enforced
- [ ] **B4.6** [GREEN] Implement `AttachmentController` in `presentation/controllers/attachment_controller.py`
  - AC: no business logic in controller; delegates to `AttachmentService`; handles exception-to-HTTP mapping
- [ ] **B4.7** [GREEN] Register routes in FastAPI router; apply EP-12 auth middleware and rate limit middleware

---

## Group 5: Celery Scan Task

- [ ] **B5.1** [RED] Write tests for `scan_attachment` Celery task:
  - ClamAV returns OK → `scan_status = 'clean'`
  - ClamAV returns FOUND → `scan_status = 'quarantined'`, S3 object tagged, admin alert sent
  - ClamAV connection error → task retried (assert retry count increments)
  - Attachment not found → task exits silently (idempotent)
  - Temp file always deleted in finally block (mock OS to verify)
  - AC: uses FakeStorageAdapter; clamd client injected (not imported directly in task)
- [ ] **B5.2** [GREEN] Implement `scan_attachment` task in `infrastructure/tasks/scan_attachment.py`
  - AC: max_retries=3; backoff 60/120/240s; temp file in system temp dir with unique name; never logs storage key or file path
- [ ] **B5.3** [RED] Write integration test: full confirm → scan → clean status path with FakeStorageAdapter + in-process Celery (CELERY_TASK_ALWAYS_EAGER=True)
- [ ] **B5.4** [GREEN] Wire `AdminNotificationService.notify_quarantine(attachment_id)` call in scan task (stub if EP-10 notification not yet available)

---

## Group 6: Celery Thumbnail Task

- [ ] **B6.1** [RED] Write tests for `generate_thumbnail` Celery task:
  - PNG input → thumbnail uploaded as JPEG 256x256 bounding box; `thumbnail_key` set on record
  - JPEG input → same
  - Non-image MIME type (PDF) → task exits without processing
  - Decompression bomb (>50MP) → `DecompressionBombError` caught, task marks attachment with `thumbnail_status='failed'` (add nullable column), does not retry
  - Corrupt image → `PIL.UnidentifiedImageError` caught, same handling
  - AC: uses FakeStorageAdapter; no real Pillow image on disk needed for unit tests (mock PIL or use real small test PNG)
- [ ] **B6.2** [GREEN] Implement `generate_thumbnail` task in `infrastructure/tasks/generate_thumbnail.py`
  - AC: `PIL.Image.MAX_IMAGE_PIXELS = 50_000_000`; aspect ratio preserved; temp file cleaned up in finally

---

## Group 7: Celery Cleanup Task

- [ ] **B7.1** [RED] Write tests for `cleanup_soft_deleted` Celery beat task:
  - Attachments soft-deleted >30 days ago → S3 objects deleted, DB records hard-deleted
  - Attachments soft-deleted <30 days ago → untouched
  - Quarantined attachments with `soft_deleted_at IS NULL` → untouched
  - S3 delete failure for one attachment → logged, others continue, `errors_count` incremented
  - Job result written to `storage_cleanup_runs`
  - AC: batch size 100; FakeStorageAdapter; FakeAttachmentRepository
- [ ] **B7.2** [GREEN] Implement `cleanup_soft_deleted` task in `infrastructure/tasks/cleanup_soft_deleted.py`
- [ ] **B7.3** [GREEN] Configure Celery beat schedule in `infrastructure/celery_config.py`: daily at 02:00 UTC

---

## Group 8: Admin Quota Endpoints

- [ ] **B8.1** [RED] Write integration tests for `GET /api/v1/admin/storage/usage`
  - Platform admin → full workspace list with stats
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

- [ ] **B9.1** [RED] Write tests for `AttachmentRateLimiter`: sliding window counter in Redis; 20 requests per hour per user; returns remaining count and reset time
  - AC: uses `FakeRedis` (fakeredis library); no real Redis in unit tests
- [ ] **B9.2** [GREEN] Implement `AttachmentRateLimiter` in `infrastructure/rate_limiting/attachment_rate_limiter.py`
  - AC: uses `ZADD`/`ZREMRANGEBYSCORE`/`ZCARD` pattern (sorted set, score=timestamp); atomic via Lua script or pipeline

---

## Group 10: Security Tests

- [ ] **B10.1** [RED] Cross-workspace attachment access: user from workspace A cannot GET/DELETE attachments from workspace B → 404
- [ ] **B10.2** [RED] MIME type bypass: server-side validation rejects even if client sends wrong MIME in request body
- [ ] **B10.3** [RED] Signed URL not in logs: assert no presigned URL appears in any log output during integration test (capture log handler)
- [ ] **B10.4** [RED] Path traversal in filename: `../../../etc/passwd` as filename → sanitized to safe key; no 500
- [ ] **B10.5** [RED] Rate limit enforcement: 21st request in 1 hour → 429
- [ ] **B10.6** [RED] Confirm by non-uploader → 403; no state change
- [ ] **B10.7** [RED] Download quarantined attachment → 422 `ATTACHMENT_NOT_AVAILABLE`
- [ ] **B10.8** [RED] Admin purge endpoint: non-admin → 403; admin → hard-delete + audit event
- [ ] **B10.9** [GREEN] Fix any failures from above security tests
- [ ] **B10.10** Workspace scoping: verify `workspace_id` from JWT is used in all DB queries (grep for queries missing workspace filter in repository layer)
