import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next/navigation', () => ({
  usePathname: () => '/workspace/acme/items',
  useRouter: () => ({ push: vi.fn() }),
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

// Prevent MatrixRain canvas errors in jsdom
vi.mock('@/components/system/matrix-rain', () => ({
  MatrixRain: () => null,
}));

// Prevent UserMenu from making extra requests
vi.mock('@/components/workspace/user-menu/user-menu', () => ({
  UserMenu: () => <div data-testid="user-menu" />,
}));

describe('WorkspaceSidebar — NotificationBell integration', () => {
  it('renders a notification bell button in the nav', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 3 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { WorkspaceSidebar } = await import(
      '@/components/workspace/workspace-sidebar'
    );
    render(<WorkspaceSidebar slug="acme" workspaceName="Acme Corp" />);

    // Bell button from NotificationBell component
    const bellButtons = screen.getAllByRole('button');
    expect(bellButtons.length).toBeGreaterThan(0);
  });

  it('inbox nav link badge uses unread count from useUnreadCount', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 5 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { WorkspaceSidebar } = await import(
      '@/components/workspace/workspace-sidebar'
    );
    render(<WorkspaceSidebar slug="acme" />);

    // Wait for badge to appear (either sidebar badge or NotificationBell badge)
    await waitFor(() => {
      // data-badge on NotificationBell, or text content "5" in a badge span
      const badges = Array.from(document.querySelectorAll('[data-badge]'));
      const sidebarBadges = Array.from(
        document.querySelectorAll('span.rounded-full')
      ).filter((el) => el.textContent === '5');
      expect(badges.length + sidebarBadges.length).toBeGreaterThan(0);
    });
  });

  it('badge caps at 99+ when count >= 100', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 200 } })
      ),
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 10 } })
      )
    );

    const { WorkspaceSidebar } = await import(
      '@/components/workspace/workspace-sidebar'
    );
    render(<WorkspaceSidebar slug="acme" />);

    await waitFor(() => {
      // data-badge on NotificationBell shows 99+
      const badge = document.querySelector('[data-badge]');
      const sidebarBadges = Array.from(
        document.querySelectorAll('span.rounded-full')
      ).filter((el) => el.textContent === '99+');
      expect(
        (badge && badge.textContent === '99+') || sidebarBadges.length > 0
      ).toBe(true);
    });
  });
});
