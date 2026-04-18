/**
 * EP-16 — Attachment types.
 * Matches backend GET /api/v1/work-items/:id/attachments response shape.
 */

export interface AttachmentResponse {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  /** Pre-formatted by backend, e.g. "200 KB" */
  size_human_readable: string;
  uploaded_by: string; // user id
  uploaded_by_name: string;
  created_at: string; // ISO 8601
  download_url: string;
  thumbnail_url?: string;
}

export interface AttachmentsListResponse {
  data: AttachmentResponse[];
}
