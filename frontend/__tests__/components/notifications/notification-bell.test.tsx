import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
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

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    const str = `${ns}.${key}`;
    if (!params) return str;
    return Object.entries(params).reduce(
      (s, [k, v]) => s.replace(`{${k}}`, String(v)),
      str,
    );
  },
}));

describe('NotificationBell', () => {
  it('renders a bell button', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    render(<NotificationBell slug="acme" />);

    expect(screen.getByRole('button')).toBeTruthy();
  });

  it('shows no badge when unreadCount is 0', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    render(<NotificationBell slug="acme" />);

    expect(document.querySelector('[data-badge]')).toBeNull();
  });

  it('shows badge with count when unreadCount > 0', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 5 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    const { waitFor } = await import('@testing-library/react');
    render(<NotificationBell slug="acme" />);

    await waitFor(() => {
      const badge = document.querySelector('[data-badge]');
      expect(badge).toBeTruthy();
      expect(badge?.textContent).toBe('5');
    });
  });

  it('caps badge at 99+ when count >= 100', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 150 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    const { waitFor } = await import('@testing-library/react');
    render(<NotificationBell slug="acme" />);

    await waitFor(() => {
      const badge = document.querySelector('[data-badge]');
      expect(badge?.textContent).toBe('99+');
    });
  });

  it('opens popover when bell is clicked', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 2 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    render(<NotificationBell slug="acme" />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    // Popover content should appear
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('shows "View all" link inside popover pointing to inbox', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 1 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    render(<NotificationBell slug="acme" />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    const viewAll = screen.getByRole('link', { name: /workspace\.notificationBell\.viewAll/i });
    expect(viewAll.getAttribute('href')).toBe('/workspace/acme/inbox');
  });

  it('shows empty state when no notifications in popover', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { NotificationBell } = await import('@/components/notifications/notification-bell');
    const { waitFor } = await import('@testing-library/react');
    render(<NotificationBell slug="acme" />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText(/workspace\.notificationBell\.empty/)).toBeTruthy();
    });
  });
});
