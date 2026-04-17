import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import WorkItemsPage from '@/app/workspace/[slug]/items/page';
import type { WorkItemResponse } from '@/lib/types/work-item';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  usePathname: () => '/workspace/acme/items',
  useParams: () => ({ slug: 'acme' }),
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
      full_name: 'Ada Lovelace',
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

const mockWorkItem: WorkItemResponse = {
  id: 'wi-1',
  title: 'Implement login flow',
  type: 'task',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 45,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-04-15T00:00:00Z',
  updated_at: '2026-04-15T10:00:00Z',
  deleted_at: null,
};

// The page needs a project_id. We stub it via workspace → project lookup.
// For simplicity the page accepts project_id from route or falls back to workspace_id.
// We test against the API endpoint used by listWorkItems.

describe('WorkItemsPage', () => {
  it('shows skeleton loading state initially', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 1, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    // skeleton should be present before data loads
    expect(document.querySelector('[data-testid="work-items-skeleton"]')).toBeInTheDocument();
  });

  it('renders work item rows after loading', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 1, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );
  });

  it('shows empty state when no items', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(
        screen.getByText(/crea tu primer elemento/i),
      ).toBeInTheDocument(),
    );
  });

  it('renders "Nuevo elemento" button linking to /workspace/acme/items/new', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    const btn = screen.getByRole('link', { name: /nuevo elemento/i });
    expect(btn).toHaveAttribute('href', '/workspace/acme/items/new');
  });

  it('navigates to item detail on row click', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 1, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByText('Implement login flow'));
    expect(mockPush).toHaveBeenCalledWith('/workspace/acme/items/wi-1');
  });

  it('renders state filter dropdown', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByTestId('work-items-skeleton')).toBeNull());
    expect(screen.getByRole('combobox', { name: /estado/i })).toBeInTheDocument();
  });
});
