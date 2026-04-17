import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import WorkspaceSelectPage from '@/app/workspace/select/page';

const mockReplace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: '1',
      email: 'a@b.com',
      full_name: 'Ada',
      avatar_url: null,
      workspace_id: 'ws-1',
      workspace_slug: 'acme',
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

const MOCK_WORKSPACES = [
  { id: 'ws-1', name: 'Acme Corp', slug: 'acme', role: 'owner' },
  { id: 'ws-2', name: 'Beta Inc', slug: 'beta', role: 'member' },
];

describe('WorkspaceSelectPage', () => {
  it('renders workspace list from GET /workspaces/mine', async () => {
    server.use(
      http.get('http://localhost/api/v1/workspaces/mine', () =>
        HttpResponse.json({ data: MOCK_WORKSPACES }),
      ),
    );
    render(<WorkspaceSelectPage />);
    await waitFor(() =>
      expect(screen.getByText('Acme Corp')).toBeInTheDocument(),
    );
    expect(screen.getByText('Beta Inc')).toBeInTheDocument();
  });

  it('selects workspace and redirects to /workspace/[slug]', async () => {
    server.use(
      http.get('http://localhost/api/v1/workspaces/mine', () =>
        HttpResponse.json({ data: MOCK_WORKSPACES }),
      ),
      http.post('http://localhost/api/v1/workspaces/select', () =>
        HttpResponse.json({ data: null }),
      ),
      http.post('http://localhost/api/v1/auth/refresh', () =>
        HttpResponse.json({ data: null }),
      ),
    );
    render(<WorkspaceSelectPage />);
    await waitFor(() =>
      expect(screen.getByText('Acme Corp')).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByText('Acme Corp'));
    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith('/workspace/acme/items'),
    );
  });
});
