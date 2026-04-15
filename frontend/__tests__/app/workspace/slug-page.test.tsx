import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import WorkspaceSlugPage from '@/app/workspace/[slug]/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockLogout = vi.fn();
let mockAuthState = {
  user: null as null | {
    id: string;
    email: string;
    full_name: string;
    avatar_url: string | null;
    workspace_id: string;
    workspace_slug: string;
    is_superadmin: boolean;
  },
  isLoading: false,
  isAuthenticated: false,
  logout: mockLogout,
};

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => mockAuthState,
}));

describe('WorkspaceSlugPage', () => {
  it('shows avatar with alt text when avatar_url is present', () => {
    mockAuthState = {
      ...mockAuthState,
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'a@b.com',
        full_name: 'Ada Lovelace',
        avatar_url: 'https://example.com/avatar.png',
        workspace_id: 'ws-1',
        workspace_slug: 'acme',
        is_superadmin: false,
      },
    };
    render(<WorkspaceSlugPage params={{ slug: 'acme' }} />);
    // UserAvatar has aria-label with the user's name
    const avatar = screen.getByRole('img', { name: 'Ada Lovelace' });
    expect(avatar).toBeTruthy();
  });

  it('shows initials when avatar_url is null', () => {
    mockAuthState = {
      ...mockAuthState,
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'a@b.com',
        full_name: 'Ada Lovelace',
        avatar_url: null,
        workspace_id: 'ws-1',
        workspace_slug: 'acme',
        is_superadmin: false,
      },
    };
    render(<WorkspaceSlugPage params={{ slug: 'acme' }} />);
    // Avatar fallback shows initials — no broken img element
    expect(screen.queryByRole('img', { name: '' })).toBeNull();
    expect(screen.getByText('AL')).toBeInTheDocument();
  });

  it('shows full_name in nav', () => {
    mockAuthState = {
      ...mockAuthState,
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'a@b.com',
        full_name: 'Ada Lovelace',
        avatar_url: null,
        workspace_id: 'ws-1',
        workspace_slug: 'acme',
        is_superadmin: false,
      },
    };
    render(<WorkspaceSlugPage params={{ slug: 'acme' }} />);
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
  });
});
