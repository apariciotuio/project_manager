/**
 * EP-23 F-4 + F-6 — Sidebar "New item" CTA + Workspace/You IA.
 *
 * F-4: primary "+ New item" CTA in the sidebar, above the profile block.
 * F-6: two zones — Workspace zone (top) with nav, You zone (bottom) with user menu.
 *      CTA sits between the zones. No duplicated controls.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { WorkspaceSidebar } from '@/components/workspace/workspace-sidebar';

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

vi.mock('@/components/system/matrix-rain', () => ({ MatrixRain: () => null }));
vi.mock('@/hooks/use-unread-count', () => ({ useUnreadCount: () => ({ count: 0 }) }));
vi.mock('@/components/notifications/notification-bell', () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));
vi.mock('@/components/workspace/user-menu/user-menu', () => ({
  UserMenu: () => <div data-testid="user-menu">UserMenu</div>,
}));

describe('WorkspaceSidebar — F-4 New item CTA', () => {
  it('renders a primary "New item" CTA linking to /workspace/{slug}/items/new', () => {
    render(<WorkspaceSidebar slug="acme" />);
    const cta = screen.getByRole('link', { name: /new item|nuevo/i });
    expect(cta).toHaveAttribute('href', '/workspace/acme/items/new');
  });

  it('CTA is rendered inside a dedicated container between the workspace zone and the you zone', () => {
    render(<WorkspaceSidebar slug="acme" />);
    const ctaRegion = screen.getByTestId('sidebar-new-item-cta');
    const workspaceZone = screen.getByTestId('sidebar-workspace-zone');
    const youZone = screen.getByTestId('sidebar-you-zone');
    expect(ctaRegion).toBeInTheDocument();
    expect(workspaceZone).toBeInTheDocument();
    expect(youZone).toBeInTheDocument();
    // DOM order: workspace → cta → you
    const sidebar = ctaRegion.closest('nav')!;
    const children = Array.from(sidebar.querySelectorAll('[data-testid]'))
      .map((el) => el.getAttribute('data-testid'))
      .filter((t): t is string =>
        t === 'sidebar-workspace-zone' ||
        t === 'sidebar-new-item-cta' ||
        t === 'sidebar-you-zone',
      );
    expect(children).toEqual([
      'sidebar-workspace-zone',
      'sidebar-new-item-cta',
      'sidebar-you-zone',
    ]);
  });
});

describe('WorkspaceSidebar — F-6 Workspace/You IA', () => {
  it('Workspace zone contains nav items (Dashboard, Items, Inbox, Teams, Admin)', () => {
    render(<WorkspaceSidebar slug="acme" />);
    const zone = screen.getByTestId('sidebar-workspace-zone');
    expect(within(zone).getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
    expect(within(zone).getByRole('link', { name: /^nav\.items/i })).toBeInTheDocument();
    expect(within(zone).getByRole('link', { name: /^nav\.inbox/i })).toBeInTheDocument();
    expect(within(zone).getByRole('link', { name: /^nav\.teams/i })).toBeInTheDocument();
    expect(within(zone).getByRole('link', { name: /^nav\.admin/i })).toBeInTheDocument();
  });

  it('You zone contains the UserMenu', () => {
    render(<WorkspaceSidebar slug="acme" />);
    const zone = screen.getByTestId('sidebar-you-zone');
    expect(within(zone).getByTestId('user-menu')).toBeInTheDocument();
  });

  it('UserMenu appears exactly once across the sidebar', () => {
    render(<WorkspaceSidebar slug="acme" />);
    expect(screen.getAllByTestId('user-menu')).toHaveLength(1);
  });

  it('New item CTA does not appear inside the Workspace zone', () => {
    render(<WorkspaceSidebar slug="acme" />);
    const zone = screen.getByTestId('sidebar-workspace-zone');
    expect(within(zone).queryByRole('link', { name: /new item|nuevo/i })).toBeNull();
  });
});
