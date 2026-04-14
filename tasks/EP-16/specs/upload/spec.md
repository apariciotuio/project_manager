# EP-16 Upload Spec — US-160, US-162

## US-160: Upload Image/Document to a Work Item

### Pre-signed URL Request

WHEN a workspace member sends `POST /api/v1/work-items/:id/attachments/request-upload` with `filename`, `mime_type`, and `size_bytes`
THEN the server validates workspace membership for the requesting user
AND validates mime_type is in the allowlist (`image/png`, `image/jpeg`, `image/gif`, `image/webp`, `application/pdf`)
AND validates `size_bytes` <= 10MB (10,485,760 bytes) or the workspace-configured override
AND validates the work item's cumulative attachment size (non-soft-deleted) + `size_bytes` <= 100MB workspace quota
AND creates an `attachments` row with `scan_status='pending'`, `work_item_id` set, `uploaded_by` set
AND returns `{ attachment_id, upload_url, expires_at }` where `upload_url` is a presigned S3 PUT URL valid for 15 minutes
AND the response does NOT appear in any server log at INFO level or above (signed URL must not be logged)

WHEN mime_type is NOT in the allowlist
THEN the server returns 422 with `{ error: { code: "ATTACHMENT_TYPE_REJECTED", message: "...", details: { allowed_types: [...] } } }`
AND no attachment record is created

WHEN `size_bytes` exceeds the per-file limit
THEN the server returns 422 with `{ error: { code: "ATTACHMENT_TOO_LARGE", message: "...", details: { max_bytes, received_bytes } } }`
AND no attachment record is created

WHEN adding this file would exceed the work item's total quota
THEN the server returns 422 with `{ error: { code: "ATTACHMENT_QUOTA_EXCEEDED", message: "...", details: { quota_bytes, current_usage_bytes, requested_bytes } } }`
AND no attachment record is created

WHEN the user has exceeded 20 upload requests in the last hour (Redis sliding window)
THEN the server returns 429 with `{ error: { code: "RATE_LIMIT_EXCEEDED", message: "..." } }`
AND `Retry-After` header is set to seconds until window resets

WHEN the work item does not exist in the user's workspace
THEN the server returns 404
AND no attachment record is created

### Client-Direct S3 Upload

WHEN the client receives a presigned PUT URL
THEN the client uploads the file binary directly to S3 with the appropriate `Content-Type` header
AND the upload does not pass through the backend server

WHEN the presigned URL has expired (> 15 minutes elapsed)
THEN S3 returns a 403 error to the client
AND the client shows an "Upload expired — please try again" message
AND the client discards the expired `attachment_id` and restarts from the request-upload step

### Upload Completion Confirmation

WHEN a client sends `POST /api/v1/attachments/:id/confirm` after a successful S3 PUT
THEN the server verifies the S3 object exists at `storage_key` via HEAD request to S3
AND the server verifies the object `Content-Length` matches the `size_bytes` recorded at request time
AND the server enqueues `scan_attachment(attachment_id)` Celery task
AND the server enqueues `generate_thumbnail(attachment_id)` Celery task (for image MIME types only)
AND the server returns 200 with `{ attachment_id, scan_status: "pending" }`

WHEN the S3 HEAD check fails (object not found)
THEN the server returns 409 with `{ error: { code: "ATTACHMENT_UPLOAD_NOT_FOUND", message: "..." } }`
AND the attachment record is NOT marked confirmed
AND the Celery tasks are NOT enqueued

WHEN `confirm` is called for an attachment that belongs to a different user
THEN the server returns 403
AND no state change occurs

WHEN `confirm` is called twice for the same attachment
THEN the second call returns 409 with `{ error: { code: "ATTACHMENT_ALREADY_CONFIRMED" } }`

### File Type Validation — Client Side

WHEN the user selects or drops a file in the upload zone
THEN the frontend checks the file's MIME type against the allowlist before initiating any server request
AND if rejected, shows an inline error: "Only PNG, JPEG, GIF, WebP, and PDF files are allowed"
AND the upload zone remains active for another attempt

WHEN the file's extension and detected MIME type disagree (e.g., `.jpg` but `application/pdf` content)
THEN the server-side MIME validation is the canonical check; client-side check is early rejection only

### Upload Progress Indicator

WHEN a file upload is in progress
THEN a progress bar shows percentage completion derived from the XMLHttpRequest/fetch upload progress event
AND upload speed (KB/s) is displayed
AND a cancel button is available

WHEN the user clicks Cancel during upload
THEN the S3 upload is aborted via `AbortController`
AND a `DELETE /api/v1/attachments/:id` request is sent to soft-delete the pending attachment record
AND the progress bar disappears

WHEN multiple files are dropped simultaneously (up to 5 at once)
THEN each file shows an independent progress bar
AND uploads run in parallel (not sequential)
AND if one fails the others continue

---

## US-162: Embed Inline Images in Comments (Paste / Drag)

### Paste from Clipboard

WHEN a user pastes an image from the clipboard into the comment editor
THEN the frontend detects the `image/*` item in `ClipboardEvent.clipboardData.items`
AND initiates the same request-upload → S3 → confirm flow as a regular attachment upload
AND `comment_id` is set on the attachment (not `work_item_id`, or both if the comment belongs to a work item)
AND while uploading, the cursor position shows a placeholder `![Uploading…]()`
AND on completion the placeholder is replaced with `![filename](signed_url)` using markdown image syntax

WHEN the pasted clipboard item is not an image (e.g., text)
THEN normal paste behaviour is preserved and no upload is triggered

WHEN the clipboard image upload fails
THEN the placeholder is replaced with `![Upload failed — try again]()`
AND the user can retry by pasting again

### Drag-Drop into Comment Editor

WHEN a user drags an image file over the comment editor
THEN the editor highlights a drop target border
AND on drop, the file is processed identically to clipboard paste (request-upload → S3 → confirm)
AND `comment_id` is set on the resulting attachment record

WHEN a non-image file type is dragged onto the comment editor
THEN the drop is rejected with a tooltip "Only images can be embedded inline"
AND the file is not uploaded

### Inline Rendering

WHEN a comment body contains `![alt](signed_url)` markdown
THEN the frontend renders the image inline within the comment
AND applies `max-width: 100%` to prevent overflow

WHEN a signed URL in a comment has expired (HTTP 403 on image load)
THEN the frontend detects the broken image and issues `GET /api/v1/attachments/:id` to fetch a fresh signed URL
AND re-renders the image with the new URL
AND the attachment `id` must be embedded in the markdown alt or a data attribute to enable this refresh

WHEN the attachment's `scan_status` is `pending`
THEN the inline position shows a spinner and "Scanning..." text
AND the frontend polls `GET /api/v1/attachments/:id` every 5 seconds until status is `clean` or `quarantined`

WHEN the attachment's `scan_status` is `quarantined`
THEN the inline position shows a warning: "File removed — failed security scan"
AND no image is rendered
