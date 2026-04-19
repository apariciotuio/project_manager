# EP-16 — v2 Carveout

**Closed as MVP-complete 2026-04-19** with the following items deliberately punted to v2:

- **File ingestion pipeline** — multipart upload handler, virus scan, storage adapter. Replaces the current "metadata CRUD only" behaviour.
- **PDF thumbnails** — renders first-page tile instead of the generic document icon.
- **Real-time scan status** — replace 5s polling with SSE push.

MVP scope shipped: attachment metadata CRUD (BE) + list/delete/drop-zone with validation (FE). Upload button shows an "upload blocked — v2" toast.

A new epic (working name "EP-26 Attachments v2") will own the ingestion pipeline when the product decides to enable uploads.
