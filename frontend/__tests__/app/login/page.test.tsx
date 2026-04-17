import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import LoginPage from '@/app/login/page';

const mockReplace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams[key] ?? null,
  }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => {
    const t: Record<string, string> = {
      'signInWithGoogle': 'Sign in with Google',
      'errors.oauth_failed': 'OAuth failed error',
      'errors.session_expired': 'Session expired error',
      'errors.invalid_state': 'Invalid state error',
      'errors.cancelled': 'Cancelled error',
      'errors.no_workspace': 'No workspace error',
    };
    return t[key] ?? key;
  },
}));

let mockSearchParams: Record<string, string> = {};
let mockAuthState = {
  user: null as null | { workspace_slug: string; full_name: string; id: string; email: string; avatar_url: null; workspace_id: string; is_superadmin: boolean },
  isLoading: false,
  isAuthenticated: false,
  logout: vi.fn(),
};

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => mockAuthState,
}));

describe('LoginPage', () => {
  beforeEach(() => {
    mockSearchParams = {};
    mockReplace.mockReset();
    mockAuthState = {
      user: null,
      isLoading: false,
      isAuthenticated: false,
      logout: vi.fn(),
    };
  });

  it('renders Google sign-in link as <a> pointing to /api/v1/auth/google', () => {
    render(<LoginPage />);
    const link = screen.getByRole('link', { name: /sign in with google/i });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute('href')).toBe('/api/v1/auth/google');
  });

  it('shows loading spinner and hides sign-in link when isLoading=true', () => {
    mockAuthState = { ...mockAuthState, isLoading: true };
    render(<LoginPage />);
    expect(screen.queryByRole('link', { name: /sign in with google/i })).toBeNull();
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('shows error banner for oauth_failed', () => {
    mockSearchParams = { error: 'oauth_failed' };
    render(<LoginPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('alert').textContent).toContain('OAuth failed error');
  });

  it('shows error banner for session_expired', () => {
    mockSearchParams = { error: 'session_expired' };
    render(<LoginPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('does NOT show error banner for unknown error param', () => {
    mockSearchParams = { error: 'some_random_error' };
    render(<LoginPage />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('does NOT show error banner when no error param', () => {
    render(<LoginPage />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('sign-in link is visible alongside error banner', () => {
    mockSearchParams = { error: 'oauth_failed' };
    render(<LoginPage />);
    expect(screen.getByRole('link', { name: /sign in with google/i })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('redirects to workspace when isAuthenticated=true', () => {
    mockAuthState = {
      ...mockAuthState,
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'a@b.com',
        full_name: 'A B',
        avatar_url: null,
        workspace_id: 'ws-1',
        workspace_slug: 'acme',
        is_superadmin: false,
      },
    };
    render(<LoginPage />);
    expect(mockReplace).toHaveBeenCalledWith('/workspace/acme');
  });

  it('does not render sign-in UI when already authenticated', () => {
    mockAuthState = {
      ...mockAuthState,
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'a@b.com',
        full_name: 'A B',
        avatar_url: null,
        workspace_id: 'ws-1',
        workspace_slug: 'acme',
        is_superadmin: false,
      },
    };
    render(<LoginPage />);
    expect(screen.queryByRole('link', { name: /sign in with google/i })).toBeNull();
  });
});
