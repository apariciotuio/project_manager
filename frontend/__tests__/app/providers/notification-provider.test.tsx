/**
 * EP-08 — NotificationProvider tests.
 * Mocks useSSENotifications + API to assert context shape and SSE event handling.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { NotificationProvider, useNotificationContext } from '@/app/providers/notification-provider';
import React from 'react';

// Mock useSSENotifications so tests control event injection
let capturedOnEvent: ((ev: { type: string; data: Record<string, unknown> }) => void) | null = null;

vi.mock('@/hooks/use-sse-notifications', () => ({
  useSSENotifications: vi.fn((onEvent: (ev: unknown) => void) => {
    capturedOnEvent = onEvent as typeof capturedOnEvent;
  }),
}));

// Mock next/navigation (used by any child that imports it)
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

const NOTIFICATION = {
  id: 'n-1',
  workspace_id: 'ws-1',
  recipient_id: 'u-1',
  type: 'review_request',
  state: 'unread',
  actor_id: 'u-2',
  subject_type: 'review',
  subject_id: 'r-1',
  deeplink: '/items/i-1',
  quick_action: null,
  extra: {},
  created_at: '2026-01-01T00:00:00Z',
  read_at: null,
  actioned_at: null,
};

beforeEach(() => {
  capturedOnEvent = null;
  server.use(
    http.get('http://localhost/api/v1/notifications', () =>
      HttpResponse.json({ data: { items: [NOTIFICATION], total: 1, page: 1, page_size: 20 } })
    ),
    http.get('http://localhost/api/v1/notifications/unread-count', () =>
      HttpResponse.json({ data: { count: 1 } })
    )
  );
});

// Consumer component to read context
function Consumer() {
  const ctx = useNotificationContext();
  return (
    <div>
      <span data-testid="unread-count">{ctx.unreadCount}</span>
      <span data-testid="notif-count">{ctx.notifications.length}</span>
      <button onClick={() => ctx.refetch()} data-testid="refetch">refetch</button>
    </div>
  );
}

describe('NotificationProvider', () => {
  it('provides context with unreadCount and notifications', async () => {
    render(
      <NotificationProvider>
        <Consumer />
      </NotificationProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('unread-count').textContent).toBe('1');
    });
  });

  it('context shape includes markRead, markActioned, executeAction, refetch', async () => {
    let ctx: ReturnType<typeof useNotificationContext> | null = null;
    function Inspector() {
      ctx = useNotificationContext();
      return null;
    }

    render(
      <NotificationProvider>
        <Inspector />
      </NotificationProvider>
    );

    await waitFor(() => {
      expect(ctx).not.toBeNull();
    });

    expect(typeof ctx!.markRead).toBe('function');
    expect(typeof ctx!.markActioned).toBe('function');
    expect(typeof ctx!.executeAction).toBe('function');
    expect(typeof ctx!.refetch).toBe('function');
  });

  it('prepends notification.created SSE event into notifications list', async () => {
    render(
      <NotificationProvider>
        <Consumer />
      </NotificationProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('notif-count').textContent).toBe('1');
    });

    const newNotif = { ...NOTIFICATION, id: 'n-2', state: 'unread' };
    act(() => {
      capturedOnEvent?.({ type: 'notification.created', data: newNotif });
    });

    await waitFor(() => {
      expect(screen.getByTestId('notif-count').textContent).toBe('2');
    });
  });

  it('updates unreadCount on notification.created SSE event', async () => {
    render(
      <NotificationProvider>
        <Consumer />
      </NotificationProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('unread-count').textContent).toBe('1');
    });

    // unread-count refetch handler should increment — mock updated response
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 2 } })
      )
    );

    const newNotif = { ...NOTIFICATION, id: 'n-2', state: 'unread' };
    act(() => {
      capturedOnEvent?.({ type: 'notification.created', data: newNotif });
    });

    await waitFor(() => {
      expect(screen.getByTestId('unread-count').textContent).toBe('2');
    });
  });

  it('throws when useNotificationContext used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Consumer />)).toThrow();
    spy.mockRestore();
  });
});
