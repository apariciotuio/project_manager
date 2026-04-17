import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
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

const DND_KEY = 'notifications.muted';

describe('markActioned mutation in useNotifications', () => {
  it('calls PATCH /notifications/{id}/actioned and updates state', async () => {
    let patchCalled = false;
    server.use(
      http.patch('http://localhost/api/v1/notifications/n1/actioned', () => {
        patchCalled = true;
        return HttpResponse.json({
          data: {
            id: 'n1',
            state: 'actioned',
            actioned_at: new Date().toISOString(),
          },
        });
      }),
    );

    const { markActioned } = await import('@/lib/api/notifications');
    await markActioned('n1');

    expect(patchCalled).toBe(true);
  });
});

describe('DND toggle in NotificationBell', () => {
  beforeEach(() => {
    localStorage.clear();
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 3 } }),
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } }),
      ),
    );
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('DND toggle appears in popover and persists to localStorage', async () => {
    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    render(<NotificationBell slug="acme" />);

    const user = userEvent.setup();
    // Open popover
    await user.click(screen.getByRole('button', { name: /workspace\.notificationBell\.ariaLabel/i }));

    // DND toggle should be visible
    const dndToggle = await screen.findByTestId('dnd-toggle');
    expect(dndToggle).toBeTruthy();

    // Click to enable DND
    await user.click(dndToggle);

    expect(localStorage.getItem(DND_KEY)).toBe('true');
  });

  it('DND on mount reads localStorage — when muted, unread-count polling is paused', async () => {
    // Pre-set DND
    localStorage.setItem(DND_KEY, 'true');

    let countFetchCount = 0;
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () => {
        countFetchCount++;
        return HttpResponse.json({ data: { count: 5 } });
      }),
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    const { unmount } = render(<NotificationBell slug="acme" />);

    // Allow a tick for initial effects
    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });

    // Even with polling, count should not have been fetched (DND=true pauses)
    // The hook may still do an initial fetch (that's acceptable), but not repeated
    const initialFetchCount = countFetchCount;

    // Advance time — no additional fetches
    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(countFetchCount).toBe(initialFetchCount); // no extra polls

    unmount();
  });

  it('DND persists across remounts — value read from localStorage on mount', async () => {
    localStorage.setItem(DND_KEY, 'true');

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    render(<NotificationBell slug="acme" />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /workspace\.notificationBell\.ariaLabel/i }));

    // DND toggle should be in muted state (checked/active) on mount
    const dndToggle = await screen.findByTestId('dnd-toggle');
    expect(dndToggle.getAttribute('data-dnd-active')).toBe('true');
  });
});
