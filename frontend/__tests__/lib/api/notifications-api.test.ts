/**
 * EP-08 — notifications-api.ts unit tests.
 * Covers stream-token and execute-action (the missing endpoints).
 * The existing notifications.ts already covers listNotifications / getUnreadCount /
 * markRead / markActioned — those are tested here as a unified surface.
 */
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import {
  listNotifications,
  getUnreadCount,
  markRead,
  markActioned,
  executeAction,
  getStreamToken,
} from '@/lib/api/notifications-api';

const NOTIFICATION_V2 = {
  id: 'n-1',
  workspace_id: 'ws-1',
  recipient_id: 'u-1',
  type: 'review_request',
  state: 'unread',
  actor_id: 'u-2',
  subject_type: 'review',
  subject_id: 'r-1',
  deeplink: '/items/i-1',
  quick_action: { action: 'Approve', endpoint: '/api/v1/reviews/r-1/approve', method: 'POST', payload_schema: {} },
  extra: {},
  created_at: '2026-01-01T00:00:00Z',
  read_at: null,
  actioned_at: null,
};

describe('listNotifications', () => {
  it('returns paginated list on 200', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('page')).toBe('1');
        expect(url.searchParams.get('page_size')).toBe('20');
        return HttpResponse.json({ data: { items: [NOTIFICATION_V2], total: 1, page: 1, page_size: 20 }, message: 'ok' });
      })
    );
    const res = await listNotifications(1, 20);
    expect(res.data.items).toHaveLength(1);
    expect(res.data.items[0]!.state).toBe('unread');
  });

  it('appends only_unread=true query param when requested', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('only_unread')).toBe('true');
        return HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 20 }, message: 'ok' });
      })
    );
    await listNotifications(1, 20, true);
  });
});

describe('getUnreadCount', () => {
  it('returns numeric count', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 7 }, message: 'ok' })
      )
    );
    const count = await getUnreadCount();
    expect(count).toBe(7);
  });
});

describe('markRead', () => {
  it('returns updated notification with state=read', async () => {
    const read = { ...NOTIFICATION_V2, state: 'read', read_at: '2026-01-02T00:00:00Z' };
    server.use(
      http.patch('http://localhost/api/v1/notifications/n-1/read', () =>
        HttpResponse.json({ data: read, message: 'ok' })
      )
    );
    const result = await markRead('n-1');
    expect(result.state).toBe('read');
    expect(result.read_at).toBeTruthy();
  });
});

describe('markActioned', () => {
  it('returns updated notification with state=actioned', async () => {
    const actioned = { ...NOTIFICATION_V2, state: 'actioned', actioned_at: '2026-01-02T00:00:00Z' };
    server.use(
      http.patch('http://localhost/api/v1/notifications/n-1/actioned', () =>
        HttpResponse.json({ data: actioned, message: 'ok' })
      )
    );
    const result = await markActioned('n-1');
    expect(result.state).toBe('actioned');
    expect(result.actioned_at).toBeTruthy();
  });
});

describe('executeAction', () => {
  it('returns actioned notification on 200', async () => {
    const actioned = { ...NOTIFICATION_V2, state: 'actioned', actioned_at: '2026-01-02T00:00:00Z' };
    server.use(
      http.post('http://localhost/api/v1/notifications/n-1/execute-action', () =>
        HttpResponse.json({ data: actioned, message: 'ok' })
      )
    );
    const result = await executeAction('n-1');
    expect(result.state).toBe('actioned');
  });

  it('throws 409 STALE_ACTION when action already executed', async () => {
    server.use(
      http.post('http://localhost/api/v1/notifications/n-1/execute-action', () =>
        HttpResponse.json(
          { error: { code: 'STALE_ACTION', message: 'action already executed' } },
          { status: 409 }
        )
      )
    );
    await expect(executeAction('n-1')).rejects.toMatchObject({ code: 'STALE_ACTION' });
  });
});

describe('getStreamToken', () => {
  it('returns token string on 200', async () => {
    server.use(
      http.post('http://localhost/api/v1/notifications/stream-token', () =>
        HttpResponse.json({ data: { token: 'tok-abc123', expires_in: 300 }, message: 'ok' })
      )
    );
    const token = await getStreamToken();
    expect(token).toBe('tok-abc123');
  });

  it('throws on 401 (unauthenticated)', async () => {
    server.use(
      http.post('http://localhost/api/v1/notifications/stream-token', () =>
        HttpResponse.json({ detail: 'not authenticated' }, { status: 401 })
      )
    );
    // 401 triggers auto-refresh; second attempt also 401 → UnauthenticatedError
    server.use(
      http.post('http://localhost/api/v1/auth/refresh', () =>
        HttpResponse.json({ detail: 'no session' }, { status: 401 })
      )
    );
    await expect(getStreamToken()).rejects.toBeDefined();
  });
});
