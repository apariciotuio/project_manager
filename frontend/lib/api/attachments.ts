/**
 * EP-16 — Attachment API client.
 * Upload intentionally absent — backend multipart handler pending.
 */
import { apiGet, apiDelete } from '../api-client';
import type { AttachmentResponse, AttachmentsListResponse } from '../types/attachment';

export async function listAttachments(workItemId: string): Promise<AttachmentResponse[]> {
  const res = await apiGet<AttachmentsListResponse>(`/api/v1/work-items/${workItemId}/attachments`);
  return res.data;
}

export async function deleteAttachment(attachmentId: string): Promise<void> {
  await apiDelete(`/api/v1/attachments/${attachmentId}`);
}
