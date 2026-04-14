# EP-16 — Technical Design: Attachments + Media

> **Resolved 2026-04-14 (decisions_pending.md #29)**: Simplified for internal/VPN deployment. Dropped: ClamAV scanner, `attachment_scan_status` state machine, SSE scan push, pending-scan-blocks-download gate, signed URLs, IAM session-tag revocation. Kept: PDF thumbnail generation, authenticated streaming endpoint, upload/download audit. Image inline paste/drag in comments supported. Object storage is S3-compatible (MinIO or AWS S3) with URL from env.

## 1. Database Schema

### `attachments` table

```sql
CREATE TABLE attachments (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    work_item_id      UUID REFERENCES work_items(id) ON DELETE SET NULL,
    comment_id        UUID REFERENCES comments(id) ON DELETE SET NULL,
    uploaded_by       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    filename          TEXT NOT NULL CHECK (char_length(filename) BETWEEN 1 AND 255),
    mime_type         TEXT NOT NULL,
    size_bytes        BIGINT NOT NULL CHECK (size_bytes > 0),
    storage_key       TEXT NOT NULL,                          -- object storage key (never logged)
    thumbnail_key     TEXT,                                   -- NULL until generated (PDFs: page 1 thumbnail)
    checksum_sha256   TEXT,                                   -- populated post-confirm via storage ETag or separate hash
    soft_deleted_at   TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT attachment_parent_required CHECK (
        work_item_id IS NOT NULL OR comment_id IS NOT NULL
    )
    -- NOTE: Both can be non-null simultaneously (inline image on a comment attached to a work item).
    -- Exclusive-OR is intentionally NOT enforced.
);
```

### Indexes

```sql
-- Primary lookup: attachments for a work item, excluding soft-deleted
CREATE INDEX idx_attachments_work_item
    ON attachments (work_item_id, created_at DESC)
    WHERE soft_deleted_at IS NULL AND work_item_id IS NOT NULL;

-- Lookup: attachments for a comment (inline images)
CREATE INDEX idx_attachments_comment
    ON attachments (comment_id)
    WHERE soft_deleted_at IS NULL AND comment_id IS NOT NULL;

-- Cleanup job: find soft-deleted attachments older than threshold
CREATE INDEX idx_attachments_cleanup
    ON attachments (soft_deleted_at ASC)
    WHERE soft_deleted_at IS NOT NULL;

-- Workspace storage usage aggregation (admin dashboard)
CREATE INDEX idx_attachments_workspace_usage
    ON attachments (workspace_id)
    WHERE soft_deleted_at IS NULL;
```

### `workspace_storage_configs` table (EP-10 pattern)

```sql
CREATE TABLE workspace_storage_configs (
    workspace_id      UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    quota_bytes       BIGINT NOT NULL DEFAULT 107374182400,  -- 100GB platform default
    per_file_max_bytes BIGINT NOT NULL DEFAULT 10485760,     -- 10MB default
    per_work_item_max_bytes BIGINT NOT NULL DEFAULT 104857600, -- 100MB default
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by        UUID REFERENCES users(id) ON DELETE SET NULL
);
```

---

## 2. Storage Adapter

### Domain Port (interface)

`domain/ports/storage_adapter.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class PresignedPutRequest:
    url: str
    expires_at: datetime
    object_key: str

@dataclass
class PresignedGetRequest:
    url: str
    expires_at: datetime

class IStorageAdapter(ABC):
    @abstractmethod
    async def generate_presigned_put(
        self,
        object_key: str,
        mime_type: str,
        size_bytes: int,
        ttl_seconds: int = 900,
    ) -> PresignedPutRequest: ...

    @abstractmethod
    async def generate_presigned_get(
        self,
        object_key: str,
        filename: str,
        disposition: str = "inline",  # "inline" | "attachment"
        ttl_seconds: int = 900,
    ) -> PresignedGetRequest: ...

    @abstractmethod
    async def object_exists(self, object_key: str) -> bool: ...

    @abstractmethod
    async def get_object_size(self, object_key: str) -> int: ...

    @abstractmethod
    async def delete_object(self, object_key: str) -> None: ...

    @abstractmethod
    async def download_to_temp(self, object_key: str) -> str:
        """Returns local file path. Caller is responsible for cleanup."""
        ...

    @abstractmethod
    async def upload_from_bytes(
        self, object_key: str, data: bytes, mime_type: str
    ) -> None: ...
```

### S3Adapter (production)

`infrastructure/adapters/s3_adapter.py` — wraps `boto3`. Key decisions:

- Constructor receives `boto3.client` (injected, not created internally) — enables FakeStorageAdapter in tests without mocking boto3 internals.
- `generate_presigned_put`: uses `generate_presigned_url('put_object', ...)` with `ContentType` and `ContentLengthRange` conditions in a policy to prevent size tampering.
- `generate_presigned_get`: uses `generate_presigned_url('get_object', ...)` with `ResponseContentDisposition` and `ResponseContentType` params.
- Object keys follow the pattern: `workspaces/{workspace_id}/attachments/{attachment_id}/{filename}` — workspace-namespaced, no path traversal possible from a UUID prefix.
- Thumbnail keys: `workspaces/{workspace_id}/attachments/{attachment_id}/thumbs/256x256.jpg`
- Never logs object keys or presigned URLs at any log level.

### FakeStorageAdapter (tests)

`tests/fakes/fake_storage_adapter.py` — in-memory dict of `object_key → bytes`. Implements `IStorageAdapter`. No network calls. Used in all unit and integration tests. Never used in production.

### MinIO (dev)

Same `S3Adapter` — MinIO exposes an S3-compatible API. Configured via environment variables (`STORAGE_ENDPOINT_URL`, `STORAGE_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`). No code change required to switch between MinIO and AWS S3.

---

## 3. Upload + Download Flow (authenticated stream, VPN)

```
Client                          Backend                          Storage / Celery
  |                                |                                 |
  |-- POST /attachments (multipart)|                                 |
  |                                |-- validate type/size/quota      |
  |                                |-- INSERT attachment row         |
  |                                |-- PUT object -----------------> |
  |                                |   (stream through BE)           |
  |                                |-- enqueue generate_thumbnail    |
  |<-- { attachment_id, ... } -----|                                 |
  |                                |                          [Celery]
  |                                |                          thumbnail → upload thumb
  |                                |                                 |
  |-- GET /attachments/:id/download|                                 |
  |                                |-- verify JWT + membership       |
  |                                |-- verify can_view_attachment    |
  |                                |-- GET object -------------------|
  |                                |-- stream response --------------|
  |<-- 200 stream body ------------|                                 |
```

No presigned URLs. The backend is a streaming proxy: it authenticates the caller, enforces workspace + capability checks, and streams the object body back with `Content-Type`, `Content-Disposition`, and ETag headers. Because the deployment is VPN-internal, this is safe; the tradeoff (more BE bandwidth for downloads) is acceptable at current scale.

### Storage Key Generation

`object_key = f"workspaces/{workspace_id}/attachments/{attachment_id}/{safe_filename}"`

`safe_filename` is the original filename with all non-alphanumeric-dot-dash characters replaced with `_`, truncated to 200 chars. The `attachment_id` UUID prefix prevents collisions and path traversal.

---

## 4. Celery Tasks

### `generate_thumbnail(attachment_id: str)`

`infrastructure/tasks/generate_thumbnail.py`

Handles images AND PDFs (page 1 for PDFs via `pdf2image` + `Pillow`, resolution #29).

1. Fetch attachment record.
2. Download object via adapter.
3. If MIME is `image/*`: open with `PIL.Image.open`. Verify format against expected MIME type (defense against polyglot files).
4. If MIME is `application/pdf`: use `pdf2image.convert_from_path(path, first_page=1, last_page=1, dpi=72)` to rasterize page 1, then continue as an image.
5. Apply `image.thumbnail((256, 256), PIL.Image.LANCZOS)` — maintains aspect ratio within 256x256 bounding box.
6. Save to in-memory `BytesIO` as JPEG (quality=85) regardless of input format.
7. Upload to `thumbnail_key` via `IStorageAdapter.upload_from_bytes`.
8. Update `thumbnail_key` on attachment record.

Pillow security: `PIL.Image.MAX_IMAGE_PIXELS = 50_000_000`. `PIL.ImageFile.LOAD_TRUNCATED_IMAGES = False`.

### `cleanup_soft_deleted()`

`infrastructure/tasks/cleanup_soft_deleted.py` — Celery beat, daily at 02:00 UTC.

1. Query: `SELECT * FROM attachments WHERE soft_deleted_at IS NOT NULL AND soft_deleted_at < now() - interval '30 days'` in batches of 100.
2. For each batch:
   a. Delete `storage_key` S3 object. Log WARNING on failure, continue.
   b. If `thumbnail_key` is not null, delete thumbnail S3 object. Log WARNING on failure, continue.
   c. Hard-delete the attachment DB record.
3. Write job result to `storage_cleanup_runs` table (last_run_at, status, attachments_purged, bytes_freed, errors_count).

---

## 5. API Endpoints

| Method | Path | Handler | Notes |
|--------|------|---------|-------|
| POST | `/api/v1/work-items/:id/attachments` | `AttachmentController.upload` | Multipart upload; BE streams to storage |
| POST | `/api/v1/comments/:id/attachments` | `AttachmentController.upload_inline` | Inline image paste/drag for comments |
| GET | `/api/v1/attachments/:id` | `AttachmentController.get` | Metadata only (no URL) |
| GET | `/api/v1/attachments/:id/download` | `AttachmentController.download` | Authenticated streaming endpoint — verifies JWT + workspace membership + `can_view_attachment`; streams body through BE. No presigned URL. |
| GET | `/api/v1/attachments/:id/thumbnail` | `AttachmentController.thumbnail` | Same auth; streams thumbnail bytes. |
| DELETE | `/api/v1/attachments/:id` | `AttachmentController.delete` | Uploader or workspace admin |
| GET | `/api/v1/work-items/:id/attachments` | `AttachmentController.list` | Workspace-scoped |
| GET | `/api/v1/admin/storage/usage` | `AdminStorageController.usage` | Platform or workspace admin |
| PATCH | `/api/v1/admin/storage/workspaces/:id/quota` | `AdminStorageController.update_quota` | Platform admin only |
| DELETE | `/api/v1/admin/attachments/:id` | `AdminStorageController.admin_delete` | Platform or workspace admin |
| DELETE | `/api/v1/admin/attachments/:id/purge` | `AdminStorageController.purge_quarantined` | Platform admin only |
| GET | `/api/v1/admin/storage/cleanup-status` | `AdminStorageController.cleanup_status` | Platform admin only |

### Response Format

Success:
```json
{
  "data": {
    "attachment_id": "uuid",
    "filename": "screenshot.png",
    "mime_type": "image/png",
    "size_bytes": 102400,
    "scan_status": "clean",
    "url": "https://s3.../...",
    "url_expires_at": "2026-04-13T10:15:00Z",
    "thumbnail_url": "https://s3.../thumbs/...",
    "created_at": "2026-04-13T10:00:00Z"
  }
}
```

Error:
```json
{
  "error": {
    "message": "File type not allowed",
    "code": "ATTACHMENT_TYPE_REJECTED",
    "details": { "allowed_types": ["image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"] }
  }
}
```

---

## 6. File Validation

### Allowed MIME Types (allowlist — not blacklist)

```python
ALLOWED_MIME_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
})
```

Client-side: check `file.type` before initiating request. Early rejection, not canonical.

Server-side canonical: validate `mime_type` from request body against `ALLOWED_MIME_TYPES`. Additionally, after confirm, the Celery thumbnail task re-validates by actually opening the file with Pillow — a file claiming to be `image/png` but containing something else will fail at processing.

### Size Limits (defaults, overridable per workspace)

| Limit | Default | Config key |
|-------|---------|------------|
| Per file | 10MB (10,485,760 bytes) | `per_file_max_bytes` |
| Per work item (total) | 100MB (104,857,600 bytes) | `per_work_item_max_bytes` |
| Platform workspace cap | 100GB | `PLATFORM_MAX_WORKSPACE_BYTES` env var |

---

## 7. Rate Limiting

Implementation: Redis sorted set sliding window (EP-12 pattern).

- Key: `rate:upload:{user_id}`
- Window: 3600 seconds
- Max requests: 20
- On exceed: return 429 + `Retry-After` header

The check happens in `AttachmentService.request_upload` before any DB write.

---

## 8. Security Considerations

| Threat | Mitigation |
|--------|-----------|
| Malicious file content | ClamAV scan before serving; file unavailable until clean |
| MIME type spoofing | Pillow re-validates image format at thumbnail generation; PDF type validated via mime magic at confirm |
| Decompression bomb (zip bomb in image) | `PIL.Image.MAX_IMAGE_PIXELS = 50_000_000` |
| Path traversal via filename | Storage key = UUID prefix + sanitized filename; UUIDs cannot be traversed |
| Signed URL leakage | 15-min TTL; never logged; `Content-Disposition` inline by default, attachment on download |
| SSRF via Pillow (processing remote URLs) | Pillow processes local temp files only; no URL loading |
| Cross-workspace access | All queries filter on `workspace_id` from JWT claims; 404 not 403 for cross-workspace to avoid leaking existence |
| Unlimited upload abuse | Rate limit 20/hour/user + per-work-item quota + workspace quota |
| Admin data leak | Storage keys never returned in admin endpoints; only metadata |

---

## 9. Integration Points

| Dependency | Integration |
|------------|-------------|
| EP-01 | `work_item_id` FK; on work item cascade delete, attachments are soft-deleted via app-layer cascade in `WorkItemService.delete` |
| EP-07 | `comment_id` FK; inline images use same attachment table with `comment_id` set |
| EP-10 | `workspace_storage_configs` follows EP-10 config pattern; admin quota UI extends EP-10 admin pages |
| EP-12 | Rate limiting middleware reused; audit events written on upload/delete/quarantine |

---

## 10. Non-functional Requirements

| Concern | Target | Approach |
|---------|--------|----------|
| Upload throughput | Direct S3 (not proxied) | Presigned PUT URL — backend not in data path |
| Thumbnail generation | < 5s p95 | Celery worker; users see spinner until ready |
| Scan latency | < 30s p95 | ClamAV local daemon; Redis-backed Celery queue |
| Signed URL generation | < 50ms | In-process boto3 call; no network round-trip |
| Storage costs | Predictable | Quota enforcement + daily cleanup of soft-deleted |
| Availability | Degrade gracefully | If ClamAV is down: retries with backoff; file stays pending; not blocked forever (max retries = 3 → mark `scan_status='scan_failed'` for manual review) |

---

## 11. Open Questions → Decisions

| Question | Decision |
|----------|----------|
| Storage provider | AWS S3 prod, MinIO dev. Adapter pattern means Cloudflare R2 is a future option with zero code change. |
| Max workspace total cap | 100GB default via `workspace_storage_configs`; platform admin can override per workspace. |
| Retention after work item archive | Attachments follow work item lifecycle. Archived work items: attachments retained. Hard-deleted work items: attachments soft-deleted (30-day cleanup). |
| PDF thumbnails | Deferred; currently shows document icon tile for PDFs. ⚠️ originally MVP-scoped — see decisions_pending.md |
| Real-time scan status push | Current: client polling (5s). Deferred: WebSocket push via EP-15 or similar. ⚠️ originally MVP-scoped — see decisions_pending.md |
