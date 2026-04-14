# EP-16 Frontend Tasks

## Group 0: Types + API Client

- [ ] **F0.1** Define TypeScript types in `types/attachments.ts`:
  - `Attachment`, `AttachmentUploadRequest`, `AttachmentUploadResponse`, `AttachmentConfirmResponse`, `ScanStatus` enum (`pending` | `clean` | `quarantined`)
  - AC: `strict: true`; no `any`
- [ ] **F0.2** [RED] Write tests for attachment API client functions: `requestUpload`, `confirmUpload`, `getAttachment`, `deleteAttachment`, `listAttachments`
  - AC: uses `msw` (Mock Service Worker) for HTTP mocking; no real network calls in tests
- [ ] **F0.3** [GREEN] Implement API client in `lib/api/attachments.ts`
  - AC: signed URLs never stored in state beyond component lifecycle; no logging of `upload_url` or `url`

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
  - `upload(file)` → calls `requestUpload`, then PUT to presigned URL with XHR progress events, then `confirmUpload`
  - Progress updates at 0%, 50%, 100% at correct XHR events
  - Cancel mid-upload → XHR aborted, `deleteAttachment` called for cleanup
  - `requestUpload` 422 ATTACHMENT_TYPE_REJECTED → error state, no XHR initiated
  - `requestUpload` 429 → rate limit error with retry-after display
  - S3 PUT fails → error state
  - `confirmUpload` S3 object not found → error state
  - Concurrent uploads (3 files) → independent state per file
  - AC: MSW for API; XHR mocked via jest `XMLHttpRequest` mock
- [ ] **F2.4** [GREEN] Implement `hooks/useUploadManager.ts`
  - AC: uses `AbortController` for cancel; `XMLHttpRequest` (not `fetch`) for progress events; signed URL never stored beyond upload lifecycle

---

## Group 3: ImageGallery + Lightbox

- [ ] **F3.1** [RED] Write tests for `ImageGallery` component:
  - Renders thumbnail grid for image attachments
  - Renders document tile with icon for PDF attachments
  - Pending attachment shows spinner overlay
  - Quarantined attachment shows warning icon; not clickable
  - Empty state when no attachments
  - "Show all (N)" link shown when count > 20
  - Click on image tile → lightbox opens
  - AC: RTL; MSW for attachment API
- [ ] **F3.2** [GREEN] Implement `components/attachments/ImageGallery.tsx`
  - Props: `workItemId: string`, `attachments: Attachment[]`, `onDelete?: (id: string) => void`
  - AC: thumbnails use `<img src={thumbnail_url}>` with `loading="lazy"`; signed URL refresh on 403 (broken image handler)
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
  - AC: no external lightbox library — implement directly (prevents unnecessary deps); focus trap via `focus-trap-react` or manual implementation

---

## Group 4: PDF Viewer

- [ ] **F4.1** [RED] Write tests for `PdfViewer` component:
  - Renders `<iframe>` with presigned URL as `src` when `navigator.pdfViewerEnabled === true`
  - Renders PDF.js fallback when `navigator.pdfViewerEnabled === false`
  - Download button present and calls `onDownload`
  - "Open in new tab" button present with correct `href`
  - URL refresh: if attachment has expired URL, fetches fresh URL before rendering
  - AC: RTL; mock `navigator.pdfViewerEnabled`
- [ ] **F4.2** [GREEN] Implement `components/attachments/PdfViewer.tsx`
  - Props: `attachment: Attachment`, `onDownload: () => void`
  - AC: PDF.js bundled (not CDN); `<iframe sandbox="allow-scripts allow-same-origin">` for native preview

---

## Group 5: Comment Editor — Inline Image Paste/Drag

- [ ] **F5.1** [RED] Write tests for `useCommentInlineImage` hook:
  - Paste event with image/png clipboardData item → triggers upload flow, inserts placeholder `![Uploading…]()`
  - Paste event with text/plain → no upload triggered
  - Upload complete → placeholder replaced with `![filename](signed_url)`
  - Upload failed → placeholder replaced with `![Upload failed — try again]()`
  - Drop image onto editor → same as paste
  - Drop non-image onto editor → rejected with tooltip text
  - AC: uses FakeStorageAdapter equivalent; no real network
- [ ] **F5.2** [GREEN] Implement `hooks/useCommentInlineImage.ts`
  - AC: `comment_id` passed to `requestUpload` when available; works with both new (no ID yet) and existing comments
- [ ] **F5.3** [RED] Write tests for inline image rendering in `CommentBody` component:
  - `![alt](url)` markdown → `<img>` rendered inline
  - Broken image (403) → fetch fresh signed URL and re-render
  - `scan_status='pending'` in attachment → spinner + polling (5s)
  - `scan_status='quarantined'` → warning message, no image
  - AC: RTL; MSW for GET /api/v1/attachments/:id
- [ ] **F5.4** [GREEN] Wire `useCommentInlineImage` into existing comment editor component
  - AC: does not break existing comment text input; paste handler is additive, not replacement

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
  - AC: bytes displayed in human-readable format (KB/MB/GB); no raw byte counts shown to users
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

## Group 8: Scan Status Polling

- [ ] **F8.1** [RED] Write tests for `useScanStatusPoller` hook:
  - Polls `GET /api/v1/attachments/:id` every 5s while `scan_status='pending'`
  - Stops polling when `scan_status` becomes `clean` or `quarantined`
  - Stops polling on component unmount (no memory leak)
  - Returns current `scan_status` and `url` (once clean)
  - AC: use `jest.useFakeTimers()` for interval; MSW
- [ ] **F8.2** [GREEN] Implement `hooks/useScanStatusPoller.ts`
  - AC: `useEffect` cleanup cancels interval; max poll duration: 5 minutes then stop (prevent infinite polling on stuck task)
