# EP-16 — Attachments + Media

## Business Need

Product work requires visual context: screenshots of bugs, mockups of features, architectural diagrams, whiteboard photos, customer-provided documents. The current MVP explicitly excludes attachments (see `assumptions.md` Q8). Users are forced to paste links to external storage, breaking the "single source of truth" principle.

Users need to attach:
- **Images** (PNG, JPG, GIF, WebP) — mockups, bugs screenshots, diagrams
- **Documents** (PDF) — specs from customers, legal docs
- **Inline images in comments** — bug reports, annotations

## Objectives

- Upload images and documents to a work item or comment
- Store in object storage (S3-compatible: AWS S3, MinIO, or similar)
- Generate thumbnails for images (async via Celery)
- Enforce file type, size, and virus scanning
- Display image gallery on the work item detail view
- Embed inline images in comments (paste from clipboard, drag-drop)
- Respect workspace isolation — signed URLs scoped to authenticated users
- Expiration: attachments deleted when their parent work item is hard-deleted

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-160 | Upload image/document to a work item | Must |
| US-161 | View attachment gallery on work item detail | Must |
| US-162 | Embed inline images in comments (paste / drag) | Must |
| US-163 | Download or preview attachments | Must |
| US-164 | Delete own attachments (uploader or owner) | Must |
| US-165 | Admin: view storage usage, enforce quotas | Should |
| US-166 | Virus scan attachments before making available | Must |

## Acceptance Criteria

- WHEN a user drags an image onto a work item THEN upload starts with progress bar
- WHEN an image uploads THEN a thumbnail is generated async, original stored in S3
- WHEN file type is not allowed THEN upload rejected at client (early) and server (canonical) with clear error
- WHEN file size exceeds limit (e.g., 10MB default) THEN rejected with specific error
- WHEN virus scan fails THEN file marked `quarantined`, not accessible to users, admin notified
- WHEN a user views attachments THEN images render inline, documents show preview icon + download
- WHEN uploader or owner deletes attachment THEN file is soft-deleted in DB, S3 object tagged for cleanup, cleanup runs in Celery beat
- AND signed URLs expire after 15 minutes (browser fetches again if cached expires)
- AND inline images in comments use the same underlying storage

## Technical Notes

- **New table**: `attachments`: id, workspace_id, work_item_id (nullable), comment_id (nullable), uploaded_by, filename, mime_type, size_bytes, storage_key, thumbnail_key, scan_status (pending/clean/quarantined), soft_deleted_at, created_at
- **One of (work_item_id, comment_id) must be non-null** — CHECK constraint
- **Object storage**: S3 (production) / MinIO (local dev) via wrapped adapter
- **Signed URLs**: pre-signed GET URLs with 15-min expiration, not direct bucket access
- **Upload flow**: client requests pre-signed PUT URL → uploads directly to S3 → notifies backend on success → backend enqueues scan + thumbnail jobs
- **Virus scan**: ClamAV via `clamd` daemon (local) or AWS GuardDuty S3 scanning (production)
- **Thumbnail**: Pillow (Python) — 256x256 for gallery, original preserved
- **Allowed types**: image/png, image/jpeg, image/gif, image/webp, application/pdf
- **Size limits**: 10MB per file, 100MB total per work item (configurable per workspace by admin)
- **Cleanup job**: Celery beat daily — hard-delete soft-deleted attachments >30 days old + orphaned S3 objects
- **Rate limiting**: 20 uploads per user per hour (prevent abuse)

## API Endpoints

- `POST /api/v1/work-items/:id/attachments/request-upload` — returns presigned URL + attachment_id
- `POST /api/v1/attachments/:id/confirm` — called by client after successful S3 upload
- `GET /api/v1/attachments/:id` — returns metadata + signed GET URL
- `DELETE /api/v1/attachments/:id` — soft delete
- `GET /api/v1/admin/storage/usage` — per-workspace stats (admin)

## Dependencies

- EP-01 (work items)
- EP-07 (comments — for inline images)
- EP-10 (admin: quotas, usage dashboard)
- EP-12 (security: file validation, rate limiting, audit)

## Complexity Assessment

**High** — New infrastructure dependency (S3/MinIO, ClamAV), upload flow with pre-signed URLs, async processing, quota enforcement, signed URL expiry management.

## Risks

- Cost: S3 storage + egress fees at scale
- Security: malicious files, SSRF via processed images (Pillow vulnerabilities), path traversal in filenames
- Performance: large files blocking uploads, thumbnail generation backlog
- Privacy: signed URL leakage if logged or shared; short expiry mitigates
- Compliance: GDPR — attachments may contain PII, need data residency control

## Open Questions

- Storage provider: AWS S3 vs MinIO vs Cloudflare R2?
- Max total storage per workspace? Per tier?
- Retention after work item archive?
