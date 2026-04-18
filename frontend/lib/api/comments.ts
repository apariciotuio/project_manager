/**
 * EP-07 — Comments API client.
 * Endpoints:
 *   GET    /api/v1/work-items/:id/comments                    — list all
 *   DELETE /api/v1/work-items/:id/comments/:comment_id        — delete
 *   GET    /api/v1/work-items/:id/sections/:section_id/comments — list by section
 */

import { apiGet, apiDelete, apiPatch } from '../api-client';
import type { Comment } from '../types/versions';

export type { Comment } from '../types/versions';

interface CommentsEnvelope {
  data: Comment[];
}

export async function listComments(workItemId: string): Promise<Comment[]> {
  const res = await apiGet<CommentsEnvelope>(
    `/api/v1/work-items/${workItemId}/comments`,
  );
  return res.data;
}

export async function deleteComment(
  workItemId: string,
  commentId: string,
): Promise<void> {
  await apiDelete<unknown>(
    `/api/v1/work-items/${workItemId}/comments/${commentId}`,
  );
}

interface UpdateCommentEnvelope {
  data: Comment;
}

export async function updateComment(
  workItemId: string,
  commentId: string,
  body: string,
): Promise<Comment> {
  const res = await apiPatch<UpdateCommentEnvelope>(
    `/api/v1/work-items/${workItemId}/comments/${commentId}`,
    { body },
  );
  return res.data;
}

export async function listSectionComments(
  workItemId: string,
  sectionId: string,
): Promise<Comment[]> {
  const res = await apiGet<CommentsEnvelope>(
    `/api/v1/work-items/${workItemId}/sections/${sectionId}/comments`,
  );
  return res.data;
}
