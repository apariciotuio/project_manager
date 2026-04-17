import { apiGet, apiPatch, apiPost } from '@/lib/api-client';
import type { NotificationV2, NotificationsV2Response, UnreadCountResponse } from '@/lib/types/api';

export type { NotificationV2, QuickAction, NotificationState } from '@/lib/types/api';

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

export async function markAllRead(): Promise<void> {
  await apiPost('/api/v1/notifications/mark-all-read', {});
}
