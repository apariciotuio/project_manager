import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { AuthProvider, useAuth } from '@/app/providers/auth-provider';
import type { AuthUser } from '@/lib/types/auth';

// Mock next/navigation router
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  usePathname: () => '/',
}));

const MOCK_USER: AuthUser = {
  id: 'user-1',
  email: 'test@example.com',
  full_name: 'Test User',
  avatar_url: null,
  workspace_id: 'ws-1',
  workspace_slug: 'acme',
  is_superadmin: false,
};

function TestConsumer() {
  const { user, isLoading, isAuthenticated } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="user">{user?.full_name ?? 'null'}</span>
    </div>
  );
}

function LogoutConsumer() {
  const { logout } = useAuth();
  return <button onClick={() => void logout()}>Logout</button>;
}

describe('AuthProvider', () => {
  it('starts with isLoading=true, isAuthenticated=false, user=null', () => {
    // Hang the /auth/me request so we can observe loading state
    server.use(
      http.get('http://localhost/api/v1/auth/me', () => {
        return new Promise(() => {}); // never resolves
      }),
    );
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    expect(screen.getByTestId('loading').textContent).toBe('true');
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(screen.getByTestId('user').textContent).toBe('null');
  });

  it('sets isAuthenticated=true and user after successful GET /auth/me', async () => {
    server.use(
      http.get('http://localhost/api/v1/auth/me', () =>
        HttpResponse.json({ data: MOCK_USER }),
      ),
    );
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('false'),
    );
    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('Test User');
  });

  it('sets isAuthenticated=false, user=null after 401 from GET /auth/me', async () => {
    server.use(
      http.get('http://localhost/api/v1/auth/me', () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'no' } },
          { status: 401 },
        ),
      ),
      // refresh will also fail (UnauthenticatedError path)
      http.post('http://localhost/api/v1/auth/refresh', () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'no' } },
          { status: 401 },
        ),
      ),
    );
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('false'),
    );
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(screen.getByTestId('user').textContent).toBe('null');
  });

  it('does NOT redirect on 401 from GET /auth/me (middleware handles it)', async () => {
    server.use(
      http.get('http://localhost/api/v1/auth/me', () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'no' } },
          { status: 401 },
        ),
      ),
      http.post('http://localhost/api/v1/auth/refresh', () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'no' } },
          { status: 401 },
        ),
      ),
    );
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('false'),
    );
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('logout calls POST /auth/logout, clears user, pushes /login', async () => {
    server.use(
      http.get('http://localhost/api/v1/auth/me', () =>
        HttpResponse.json({ data: MOCK_USER }),
      ),
      http.post('http://localhost/api/v1/auth/logout', () =>
        HttpResponse.json({ data: null }),
      ),
    );
    render(
      <AuthProvider>
        <TestConsumer />
        <LogoutConsumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('authenticated').textContent).toBe('true'),
    );
    await act(async () => {
      screen.getByRole('button', { name: 'Logout' }).click();
    });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/login'));
    expect(screen.getByTestId('user').textContent).toBe('null');
  });

  it('logout redirects even when API call fails', async () => {
    server.use(
      http.get('http://localhost/api/v1/auth/me', () =>
        HttpResponse.json({ data: MOCK_USER }),
      ),
      http.post('http://localhost/api/v1/auth/logout', () =>
        HttpResponse.json(
          { error: { code: 'SERVER_ERROR', message: 'oops' } },
          { status: 500 },
        ),
      ),
    );
    render(
      <AuthProvider>
        <TestConsumer />
        <LogoutConsumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('authenticated').textContent).toBe('true'),
    );
    await act(async () => {
      screen.getByRole('button', { name: 'Logout' }).click();
    });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/login'));
  });
});

describe('useAuth outside provider', () => {
  it('throws descriptive error', () => {
    function Naked() {
      useAuth();
      return null;
    }
    // Suppress React's error boundary console output
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Naked />)).toThrow(/AuthProvider/);
    consoleSpy.mockRestore();
  });
});
