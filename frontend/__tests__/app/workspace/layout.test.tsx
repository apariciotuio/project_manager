import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WorkspaceLayout from '@/app/workspace/[slug]/layout';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  usePathname: () => '/workspace/acme/items',
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockLogout = vi.fn();

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: '1',
      email: 'a@b.com',
      full_name: 'Ada Lovelace',
      avatar_url: null,
      workspace_id: 'ws-1',
      workspace_slug: 'acme',
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
    logout: mockLogout,
  }),
}));

// Stub notification hook so layout.test doesn't need MSW
vi.mock('@/hooks/use-notifications', () => ({
  useNotifications: () => ({ unreadCount: 0, isLoading: false }),
}));

describe('WorkspaceLayout', () => {
  it('renders nav items for Items, Inbox, Teams, Admin', () => {
    render(
      <WorkspaceLayout params={{ slug: 'acme' }}>
        <div>content</div>
      </WorkspaceLayout>,
    );
    // next-intl mock returns key as-is, so t('items') → 'items'
    expect(screen.getByRole('link', { name: /items/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /inbox/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /teams/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /admin/i })).toBeInTheDocument();
  });

  it('renders children in main content area', () => {
    render(
      <WorkspaceLayout params={{ slug: 'acme' }}>
        <div data-testid="child-content">child</div>
      </WorkspaceLayout>,
    );
    expect(screen.getByTestId('child-content')).toBeInTheDocument();
  });

  it('renders the user menu trigger (avatar) in sidebar footer', () => {
    render(
      <WorkspaceLayout params={{ slug: 'acme' }}>
        <div>content</div>
      </WorkspaceLayout>,
    );
    // Avatar has aria-label with the user name
    expect(screen.getByRole('img', { name: /ada lovelace/i })).toBeInTheDocument();
  });

  it('calls logout when sign-out is selected from user menu', async () => {
    render(
      <WorkspaceLayout params={{ slug: 'acme' }}>
        <div>content</div>
      </WorkspaceLayout>,
    );
    // next-intl mock returns key as-is: t('triggerAria') → 'triggerAria'
    const menuTrigger = screen.getByRole('button', { name: /triggerAria/i });
    await userEvent.click(menuTrigger);
    const signOutItem = screen.getByRole('menuitem', { name: /signOut/i });
    await userEvent.click(signOutItem);
    expect(mockLogout).toHaveBeenCalledOnce();
  });

  it('highlights active nav item based on pathname', () => {
    render(
      <WorkspaceLayout params={{ slug: 'acme' }}>
        <div>content</div>
      </WorkspaceLayout>,
    );
    const itemsLink = screen.getByRole('link', { name: /items/i });
    // active link should have aria-current="page"
    expect(itemsLink).toHaveAttribute('aria-current', 'page');
  });
});
