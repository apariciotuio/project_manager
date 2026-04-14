# EP-16 Gallery Spec — US-161, US-163

## US-161: View Attachment Gallery on Work Item Detail

### Gallery Rendering

WHEN a user opens a work item detail page
THEN the attachments section renders below the work item body
AND image attachments (PNG, JPEG, GIF, WebP) are displayed as thumbnail grid (256x256 tiles)
AND PDF attachments are displayed as a document tile with a PDF icon and filename
AND attachments with `scan_status='pending'` show a spinner overlay on their tile with "Scanning..." text
AND attachments with `scan_status='quarantined'` show a warning icon and are not clickable
AND soft-deleted attachments are not returned by the API and not rendered

WHEN no attachments exist for the work item
THEN the attachments section renders an empty state: "No attachments yet — drag files here to upload"

WHEN the work item has more than 20 attachments
THEN the gallery shows the 20 most recent by `created_at DESC`
AND a "Show all (N)" link loads the full paginated list

WHEN `thumbnail_key` is NULL (thumbnail not yet generated or non-image)
THEN the tile renders a generic file-type icon instead of the thumbnail
AND once the thumbnail Celery task completes, the tile updates on next page load (no real-time push for MVP)

### Thumbnail Click — Fullscreen Viewer (Images)

WHEN a user clicks an image thumbnail in the gallery
THEN a fullscreen lightbox overlay opens showing the full-resolution image
AND the overlay has a close button (X) and is closeable via Escape key
AND left/right arrow navigation buttons appear if there are multiple image attachments
AND the filename and upload date are shown in the overlay footer
AND the URL does NOT change (no router push — lightbox is a local modal state)

WHEN the user presses the left arrow key or clicks the left navigation button
THEN the previous image attachment in gallery order is displayed

WHEN the user presses the right arrow key or clicks the right navigation button
THEN the next image attachment in gallery order is displayed

WHEN the user reaches the first or last image
THEN the corresponding navigation button is disabled (no wraparound)

WHEN the user clicks outside the lightbox image area
THEN the lightbox closes

### PDF Preview

WHEN a user clicks a PDF attachment tile
THEN an inline PDF preview panel opens (not a new tab) using the browser's native PDF viewer via `<iframe>` or `<embed>` with the presigned GET URL as `src`
AND the panel has a minimum height of 600px and is scrollable
AND a "Download" button is present in the preview panel header
AND a "Open in new tab" button is present

WHEN the browser does not support inline PDF rendering (detected via `navigator.pdfViewerEnabled === false`)
THEN the fallback shows a PDF.js-based preview (bundled component, not CDN)

WHEN the presigned URL for the PDF has expired before the preview panel opens
THEN `GET /api/v1/attachments/:id` is called to refresh the URL before injecting it into the `src`

---

## US-163: Download or Preview Attachments

### Download Button

WHEN a user clicks "Download" on any attachment (from gallery tile or lightbox or PDF preview)
THEN `GET /api/v1/attachments/:id` is called
AND the response includes `{ download_url, filename, mime_type, size_bytes }`
AND `download_url` is a presigned GET URL with `Content-Disposition: attachment; filename="..."` header set at S3 object level
AND the browser initiates a download using a programmatic `<a href download>` click
AND the signed URL is NOT stored in browser history or any persistent log

WHEN the attachment's `scan_status` is NOT `clean`
THEN `GET /api/v1/attachments/:id` returns 422 with `{ error: { code: "ATTACHMENT_NOT_AVAILABLE", message: "File is unavailable (scan pending or quarantined)" } }`
AND no download URL is returned

WHEN the user requesting the download does not belong to the attachment's workspace
THEN the server returns 403

### Keyboard Navigation (Lightbox)

WHEN the lightbox is open
THEN keyboard events are captured and the following bindings apply:
AND `Escape` → close lightbox
AND `ArrowLeft` → previous image
AND `ArrowRight` → next image
AND `d` → trigger download for current attachment
AND keyboard focus is trapped within the lightbox while open (accessibility — focus must not leak to background content)

WHEN the lightbox is closed
THEN keyboard events revert to page-level defaults
AND focus returns to the thumbnail that was clicked to open the lightbox
