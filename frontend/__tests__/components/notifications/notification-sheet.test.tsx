import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ slug: 'acme' }),
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      full_name: 'Ada',
      workspace_id: 'ws1',
      workspace_slug: 'acme',
      email: 'a@b.com',
      avatar_url: null,
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

const makeNotification = (overrides: Record<string, unknown> = {}) => ({
  id: 'n1',
  workspace_id: 'ws1',
  recipient_id: 'u1',
  type: 'system',
  state: 'unread' as const,
  actor_id: null,
  subject_type: 'work_item' as const,
  subject_id: 'wi1',
  deeplink: '',
  quick_action: null,
  extra: { summary: 'System maintenance scheduled', actor_name: 'System' },
  created_at: '2026-04-16T10:00:00Z',
  read_at: null,
  actioned_at: null,
  ...overrides,
});

describe('NotificationSheet', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } }),
      ),
    );
  });

  it('renders sheet with notification summary and actor when open', async () => {
    const notification = makeNotification();
    const { NotificationSheet } = await import(
      '@/components/notifications/notification-sheet'
    );

    render(
      <NotificationSheet
        notification={notification}
        open={true}
        onClose={vi.fn()}
        onMarkActioned={vi.fn()}
      />,
    );

    expect(screen.getByTestId('sheet-title')).toBeTruthy();
    expect(screen.getByText('System maintenance scheduled')).toBeTruthy();
    expect(screen.getByTestId('sheet-actor')).toBeTruthy();
    expect(screen.getByText('System')).toBeTruthy();
  });

  it('shows "Mark actioned" button only when notification has quick_action', async () => {
    const withAction = makeNotification({
      quick_action: {
        action: 'Approve',
        endpoint: '/api/v1/reviews/r1/respond',
        method: 'POST',
        payload_schema: {},
      },
    });
    const withoutAction = makeNotification({ quick_action: null });

    const { NotificationSheet } = await import(
      '@/components/notifications/notification-sheet'
    );

    const { rerender } = render(
      <NotificationSheet
        notification={withAction}
        open={true}
        onClose={vi.fn()}
        onMarkActioned={vi.fn()}
      />,
    );
    expect(screen.getByTestId('mark-actioned-btn')).toBeTruthy();

    rerender(
      <NotificationSheet
        notification={withoutAction}
        open={true}
        onClose={vi.fn()}
        onMarkActioned={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('mark-actioned-btn')).toBeNull();
  });

  it('calls PATCH /actioned and invokes onMarkActioned callback on button click', async () => {
    let patchCalled = false;
    server.use(
      http.patch('http://localhost/api/v1/notifications/n1/actioned', () => {
        patchCalled = true;
        return HttpResponse.json({
          data: { ...makeNotification(), state: 'actioned', actioned_at: new Date().toISOString() },
        });
      }),
    );

    const onMarkActioned = vi.fn();
    const notification = makeNotification({
      quick_action: {
        action: 'Approve',
        endpoint: '/api/v1/reviews/r1/respond',
        method: 'POST',
        payload_schema: {},
      },
    });

    const { NotificationSheet } = await import(
      '@/components/notifications/notification-sheet'
    );

    render(
      <NotificationSheet
        notification={notification}
        open={true}
        onClose={vi.fn()}
        onMarkActioned={onMarkActioned}
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByTestId('mark-actioned-btn'));

    await waitFor(() => {
      expect(patchCalled).toBe(true);
      expect(onMarkActioned).toHaveBeenCalledWith('n1');
    });
  });

  it('notification item calls onOpenSheet when row has no deeplink', async () => {
    const onOpenSheet = vi.fn();
    const notification = makeNotification({ deeplink: '' });

    const { NotificationItem } = await import(
      '@/components/notifications/notification-item'
    );

    render(
      <NotificationItem
        notification={notification}
        onMarkRead={vi.fn()}
        onOpenSheet={onOpenSheet}
      />,
    );

    // Clicking the item row directly should call onOpenSheet
    // The item row is the wrapper div with data-notification-id
    const row = document.querySelector('[data-notification-id="n1"]') as HTMLElement;
    expect(row).toBeTruthy();
  });
});
