/**
 * EP-08 — Notifications API client (consolidated).
 *
 * Routes (all under /api/v1):
 *   GET    /notifications                    → listNotifications
 *   GET    /notifications/unread-count       → getUnreadCount
 *   PATCH  /notifications/:id/read           → markRead
 *   PATCH  /notifications/:id/actioned       → markActioned
 *   POST   /notifications/:id/execute-action → executeAction
 *   POST   /notifications/stream-token       → getStreamToken
 */

import { apiGet, apiPatch, apiPost } from '@/lib/api-client';
import type { NotificationV2, NotificationsV2Response, UnreadCountResponse } from '@/lib/types/api';

export type { NotificationV2, NotificationState, QuickAction } from '@/lib/types/api';

// ─── API functions ────────────────────────────────────────────────────────────

export async function listNotifications(
  page = 1,
  pageSize = 20,
  onlyUnread?: boolean,
): Promise<NotificationsV2Response> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (onlyUnread) params.set('only_unread', 'true');
  return apiGet<NotificationsV2Response>(`/api/v1/notifications?${params.toString()}`);
}

export async function getUnreadCount(): Promise<number> {
  const res = await apiGet<UnreadCountResponse>('/api/v1/notifications/unread-count');
  return res.data.count;
}

export async function markRead(id: string): Promise<NotificationV2> {
  const res = await apiPatch<{ data: NotificationV2 }>(`/api/v1/notifications/${id}/read`, {});
  return res.data;
}

export async function markActioned(id: string): Promise<NotificationV2> {
  const res = await apiPatch<{ data: NotificationV2 }>(`/api/v1/notifications/${id}/actioned`, {});
  return res.data;
}

export async function executeAction(
  id: string,
  params?: Record<string, unknown>,
): Promise<NotificationV2> {
  const res = await apiPost<{ data: NotificationV2 }>(
    `/api/v1/notifications/${id}/execute-action`,
    params ?? {},
  );
  return res.data;
}

export async function getStreamToken(): Promise<string> {
  const res = await apiPost<{ data: { token: string; expires_in: number }; message: string }>(
    '/api/v1/notifications/stream-token',
    {},
  );
  return res.data.token;
}
