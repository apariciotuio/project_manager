import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useNotifications } from '@/hooks/use-notifications';

const mockNotifications = [
  {
    id: 'n1',
    type: 'mention',
    actor_name: 'Alice',
    summary: 'Alice mentioned you',
    deeplink: '/workspace/acme/items/i1',
    read: false,
    created_at: '2026-04-16T10:00:00Z',
  },
  {
    id: 'n2',
    type: 'assignment',
    actor_name: 'Bob',
    summary: 'Bob assigned you',
    deeplink: null,
    read: true,
    created_at: '2026-04-15T09:00:00Z',
  },
];

describe('useNotifications', () => {
  it('returns notifications on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: mockNotifications })
      )
    );

    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.notifications).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'nope' } }, { status: 403 })
      )
    );

    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
  });

  it('markRead optimistically sets notification.read=true', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: mockNotifications })
      ),
      http.patch('http://localhost/api/v1/notifications/n1/read', () =>
        HttpResponse.json({}, { status: 200 })
      )
    );

    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.notifications.find((n) => n.id === 'n1')?.read).toBe(false);

    await act(async () => {
      await result.current.markRead('n1');
    });

    expect(result.current.notifications.find((n) => n.id === 'n1')?.read).toBe(true);
  });

  it('unread notifications have read=false', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: mockNotifications })
      )
    );

    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const unread = result.current.notifications.filter((n) => !n.read);
    expect(unread).toHaveLength(1);
    expect(unread[0]!.id).toBe('n1');
  });
});
