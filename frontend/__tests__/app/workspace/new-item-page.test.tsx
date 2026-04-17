import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useParams: () => ({ slug: 'acme' }),
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'u1', full_name: 'Ada', workspace_id: 'ws1', workspace_slug: 'acme', email: 'a@b.com', avatar_url: null, is_superadmin: false },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

function setupHandlers() {
  server.use(
    http.get('http://localhost/api/v1/templates', () =>
      HttpResponse.json({
        data: [
          { id: 't1', name: 'Bug Report', description: null, type: 'bug', fields: {} },
          { id: 't2', name: 'Feature', description: 'Feature template', type: 'enhancement', fields: {} },
        ],
      })
    ),
    http.post('http://localhost/api/v1/drafts', () =>
      HttpResponse.json({ data: { id: 'draft1', title: null, type: null, description: null, updated_at: new Date().toISOString() } })
    ),
    http.patch('http://localhost/api/v1/drafts/draft1', () =>
      HttpResponse.json({ data: { id: 'draft1', title: 'My item', type: 'bug', description: '', updated_at: new Date().toISOString() } })
    ),
    http.post('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({ data: { id: 'wi1', title: 'My item', type: 'bug', state: 'draft', created_at: new Date().toISOString() } })
    )
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('NewItemPage', () => {
  it('renders the title input', async () => {
    setupHandlers();
    const { default: NewItemPage } = await import('@/app/workspace/[slug]/items/new/page');
    render(<NewItemPage params={{ slug: 'acme' }} />);

    expect(await screen.findByPlaceholderText(/título/i)).toBeTruthy();
  });

  it('renders templates after load', async () => {
    setupHandlers();
    const { default: NewItemPage } = await import('@/app/workspace/[slug]/items/new/page');
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByText('Bug Report')).toBeTruthy();
    });
  });

  it('create button is disabled when title is empty', async () => {
    setupHandlers();
    const { default: NewItemPage } = await import('@/app/workspace/[slug]/items/new/page');
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/título/i);
    const btn = screen.getByRole('button', { name: /crear/i });
    expect(btn).toBeDisabled();
  });

  it('submits work item and redirects', async () => {
    setupHandlers();
    const { default: NewItemPage } = await import('@/app/workspace/[slug]/items/new/page');
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const titleInput = await screen.findByPlaceholderText(/título/i);
    await userEvent.type(titleInput, 'My item');

    const btn = screen.getByRole('button', { name: /crear/i });
    await userEvent.click(btn);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/workspace/acme/items/wi1');
    });
  });
});
