/**
 * EP-03 — Thread API client functions.
 * Endpoints: GET/POST /api/v1/threads, GET /api/v1/threads/{id}/history, DELETE /api/v1/threads/{id}
 */

import { apiGet, apiPost, apiDelete } from '../api-client';
import type { ConversationThread, ConversationMessage } from '../types/conversation';

interface Envelope<T> {
  data: T;
}

export async function getThreads(workItemId?: string): Promise<ConversationThread[]> {
  const params = new URLSearchParams();
  if (workItemId) params.set('work_item_id', workItemId);
  const qs = params.toString();
  const res = await apiGet<Envelope<ConversationThread[]>>(
    `/api/v1/threads${qs ? `?${qs}` : ''}`,
  );
  return res.data;
}

export async function createThread(data: {
  work_item_id?: string;
}): Promise<ConversationThread> {
  const res = await apiPost<Envelope<ConversationThread>>('/api/v1/threads', data);
  return res.data;
}

export async function getThreadHistory(threadId: string): Promise<ConversationMessage[]> {
  const res = await apiGet<Envelope<ConversationMessage[]>>(
    `/api/v1/threads/${threadId}/history`,
  );
  return res.data;
}

export async function archiveThread(threadId: string): Promise<void> {
  await apiDelete<void>(`/api/v1/threads/${threadId}`);
}
