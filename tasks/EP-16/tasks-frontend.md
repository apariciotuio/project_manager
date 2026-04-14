# EP-16 Frontend Tasks

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `TypedConfirmDialog` (delete confirmation), `HumanError` (upload failures, type/size rejection), `EmptyStateWithCTA` (gallery empty state), `CopyButton` (copy markdown reference). Upload drop-zone, progress UI, lightbox, and PDF viewer stay feature-specific. Semantic tokens and i18n `i18n/es/attachment.ts`. See `tasks/extensions.md#EP-19`.

> **Scope (2026-04-14, decisions_pending.md #29)**: VPN-internal deployment. **Dropped**: scan-status polling (`useScanStatusPoller`), scan-status UI states (`pending`/`quarantined`), presigned URL handling, signed URL refresh on 403, two-phase `request-upload`+`confirm` flow. **Kept**: drag/drop + paste upload, progress UI, image gallery, PDF viewer (inline + download), inline comment images, admin quota dashboard, delete with confirmation. Below is rewritten — obsolete groups removed, not flagged.

---

## Group 0: Types + API Client

- [ ] **F0.1** Define TypeScript types in `types/attachments.ts`:
  - `Attachment { id, filename, mime_type, size_bytes, thumbnail_url?, download_url, uploaded_by, created_at }`. No `ScanStatus` enum (decision #29).
  - AC: `strict: true`; no `any`
- [ ] **F0.2** [RED] Write tests for attachment API client functions: `uploadAttachment(workItemId, file, onProgress, signal)`, `getAttachment`, `deleteAttachment`, `listAttachments`
  - AC: uses `msw` (Mock Service Worker) for HTTP mocking; no real network calls in tests
- [ ] **F0.3** [GREEN] Implement API client in `lib/api/attachments.ts`
  - `download_url` is always the backend streaming endpoint (`/api/v1/attachments/:id/download`); never a presigned URL
  - `uploadAttachment` is a single multipart POST to `/api/v1/work-items/:id/attachments` with `XMLHttpRequest` for progress events; no `request-upload` / `confirm` two-phase flow

---

## Group 1: AttachmentDropZone

- [ ] **F1.1** [RED] Write tests for `AttachmentDropZone` component:
  - Renders drop target area with correct label
  - `dragover` → visual highlight applied
  - `dragleave` → highlight removed
  - Drop with valid file type → `onFilesSelected` callback called with `File[]`
  - Drop with invalid file type → inline error shown; callback NOT called
  - File input click (non-drag) → same validation + callback
  - Multiple files dropped (up to 5) → all passed to callback
  - AC: uses React Testing Library; no real uploads in component tests
- [ ] **F1.2** [GREEN] Implement `components/attachments/AttachmentDropZone.tsx`
  - Props: `onFilesSelected: (files: File[]) => void`, `allowedMimeTypes: string[]`, `maxFileSizeBytes: number`, `disabled?: boolean`
  - AC: client-side MIME type check before calling `onFilesSelected`; accessible (`role="button"`, `aria-label`, keyboard-activatable)
- [ ] **F1.3** [REFACTOR] Extract `useFileDrop(config)` hook to decouple drop logic from rendering; reuse in comment editor

---

## Group 2: UploadProgress

- [ ] **F2.1** [RED] Write tests for `UploadProgress` component:
  - Renders progress bar at 0%, 50%, 100%
  - Shows filename and upload speed (KB/s)
  - Cancel button calls `onCancel` callback
  - Upload complete state shows checkmark and hides progress bar
  - Error state shows error message with retry option
  - AC: RTL; snapshot for each state variant
- [ ] **F2.2** [GREEN] Implement `components/attachments/UploadProgress.tsx`
  - Props: `filename: string`, `progress: number` (0-100), `speedKbps?: number`, `status: 'uploading' | 'complete' | 'error'`, `errorMessage?: string`, `onCancel: () => void`, `onRetry?: () => void`
- [ ] **F2.3** [RED] Write tests for `useUploadManager` hook:
  - `upload(file)` → single multipart POST to `/api/v1/work-items/:id/attachments` with XHR progress events; on success returns the `Attachment` metadata
  - Progress updates at 0%, 50%, 100% at correct XHR events
  - Cancel mid-upload → XHR aborted; no partial attachment left
  - 422 `ATTACHMENT_TYPE_REJECTED` → error state
  - 413 `ATTACHMENT_TOO_LARGE` → error state
  - 429 → rate-limit error with `Retry-After` display
  - Concurrent uploads (3 files) → independent state per file
  - AC: MSW for API; XHR mocked via jest `XMLHttpRequest` mock
- [ ] **F2.4** [GREEN] Implement `hooks/useUploadManager.ts`
  - AC: uses `AbortController` for cancel; `XMLHttpRequest` (not `fetch`) for progress events

---

## Group 3: ImageGallery + Lightbox

- [ ] **F3.1** [RED] Write tests for `ImageGallery` component:
  - Renders thumbnail grid for image attachments
  - Renders document tile with icon for PDF attachments; PDF thumbnails (first page) rendered when `thumbnail_url` present
  - Empty state when no attachments
  - "Show all (N)" link shown when count > 20
  - Click on image tile → lightbox opens
  - AC: RTL; MSW for attachment API
  - Removed: `pending` spinner overlay, `quarantined` warning icon (decision #29)
- [ ] **F3.2** [GREEN] Implement `components/attachments/ImageGallery.tsx`
  - Props: `workItemId: string`, `attachments: Attachment[]`, `onDelete?: (id: string) => void`
  - AC: thumbnails use `<img src={thumbnail_url}>` with `loading="lazy"`; `thumbnail_url` is the backend streaming endpoint; on 204 fall back to generic icon; no 403 refresh flow (no presigned URLs)
- [ ] **F3.3** [RED] Write tests for `Lightbox` component:
  - Opens with correct image
  - Left/right navigation between images
  - First image: left button disabled; last image: right button disabled
  - Escape key closes lightbox
  - Click outside image area closes lightbox
  - `d` key triggers download
  - Focus trapped while open; focus returned to trigger element on close
  - `aria-modal="true"`, `role="dialog"` present
  - AC: RTL with `userEvent`; keyboard events tested
- [ ] **F3.4** [GREEN] Implement `components/attachments/Lightbox.tsx`
  - Props: `images: Attachment[]`, `initialIndex: number`, `onClose: () => void`, `onDownload: (id: string) => void`

---

## Group 4: PDF Viewer

- [ ] **F4.1** [RED] Write tests for `PdfViewer` component:
  - Renders `<iframe src={download_url}>` when `navigator.pdfViewerEnabled === true` (browser-native viewer)
  - Renders PDF.js fallback when `navigator.pdfViewerEnabled === false`
  - Download button present and calls `onDownload`
  - "Open in new tab" button present with `href={download_url}` (backend streaming endpoint — JWT cookie must accompany for auth)
  - No URL refresh flow — `download_url` is a stable backend path, not a presigned URL
  - AC: RTL; mock `navigator.pdfViewerEnabled`
- [ ] **F4.2** [GREEN] Implement `components/attachments/PdfViewer.tsx`
  - Props: `attachment: Attachment`, `onDownload: () => void`
  - AC: PDF.js bundled (not CDN); `<iframe sandbox="allow-scripts allow-same-origin">` for native preview

---

## Group 5: Comment Editor — Inline Image Paste/Drag

- [ ] **F5.1** [RED] Write tests for `useCommentInlineImage` hook:
  - Paste event with `image/*` clipboardData item → triggers multipart upload, inserts placeholder `![Uploading…]()`
  - Paste event with `text/plain` → no upload triggered
  - Upload complete → placeholder replaced with `![filename](attachment_id)` (BE renders the image by substituting `attachment_id` to the download endpoint)
  - Upload failed → placeholder replaced with `![Upload failed — try again]()`
  - Drop image onto editor → same as paste
  - Drop non-image onto editor → rejected with tooltip text
  - AC: MSW for API; no real network
- [ ] **F5.2** [GREEN] Implement `hooks/useCommentInlineImage.ts`
  - AC: `comment_id` (when available) or `work_item_id` passed to upload endpoint
- [ ] **F5.3** [RED] Write tests for inline image rendering in `CommentBody` component:
  - `![alt](attachment_id)` markdown → `<img src={/api/v1/attachments/:id/download}>` rendered inline
  - Soft-deleted image → EP-07 BE substitution omits the ref; rendered as placeholder text
  - Removed: scan-status polling (5s), pending spinner, quarantined warning (decision #29)
  - AC: RTL; MSW for GET /api/v1/attachments/:id
- [ ] **F5.4** [GREEN] Wire `useCommentInlineImage` into existing comment editor component
  - AC: paste handler is additive, not a replacement for text input

---

## Group 6: Admin Storage Dashboard

- [ ] **F6.1** [RED] Write tests for `StorageUsageDashboard` component:
  - Renders table with workspace rows sorted by usage DESC by default
  - Quota utilization bar shown (color-coded: green < 70%, yellow 70-90%, red > 90%)
  - Sort controls for `total_bytes`, `quota_utilization`, `file_count`
  - Pagination: "Load more" button
  - Workspace admin sees only own workspace row
  - AC: RTL; MSW for `GET /api/v1/admin/storage/usage`
- [ ] **F6.2** [GREEN] Implement `components/admin/StorageUsageDashboard.tsx`
  - AC: bytes displayed in human-readable format (KB/MB/GB)
- [ ] **F6.3** [RED] Write tests for `WorkspaceQuotaEditor` component:
  - Renders current quota with edit button
  - Edit mode: input field + save/cancel
  - Save → PATCH request → success toast
  - Validation: negative quota rejected; quota > platform max rejected with error message
  - AC: RTL; MSW
- [ ] **F6.4** [GREEN] Implement `components/admin/WorkspaceQuotaEditor.tsx`
- [ ] **F6.5** [RED] Write tests for `CleanupJobStatus` component:
  - `never_run` → descriptive message
  - `success` → stats displayed
  - `running` → spinner + partial count
  - `failure` → error message + error detail (truncated)
  - AC: RTL
- [ ] **F6.6** [GREEN] Implement `components/admin/CleanupJobStatus.tsx`

---

## Group 7: Deletion UI with Confirmation

- [ ] **F7.1** [RED] Write tests for `AttachmentDeleteButton` component:
  - Renders delete icon button
  - Click → confirmation dialog opens with attachment filename
  - Confirm → `DELETE /api/v1/attachments/:id` called; attachment removed from gallery
  - Cancel → no deletion; dialog closed
  - Loading state during delete request
  - Error state if DELETE fails (non-404)
  - AC: RTL; MSW
- [ ] **F7.2** [GREEN] Implement `components/attachments/AttachmentDeleteButton.tsx`
  - Props: `attachment: Attachment`, `onDeleted: (id: string) => void`
  - AC: only shown to uploaders and workspace admins (check from attachment `uploaded_by` vs current user ID); optimistic removal from list on success

---

## Group 8: (removed — no scan-status polling per decision #29)

`useScanStatusPoller`, 5s polling, pending/quarantined UI states — **all out of scope**. VPN-internal deployment; attachments are available immediately after upload returns 201.
