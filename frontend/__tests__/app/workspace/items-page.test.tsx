import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import WorkItemsPage from '@/app/workspace/[slug]/items/page';
import type { WorkItemResponse } from '@/lib/types/work-item';

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams: Record<string, string> = {};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => '/workspace/acme/items',
  useParams: () => ({ slug: 'acme' }),
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams[key] ?? null,
    getAll: (key: string) => (mockSearchParams[key] ? [mockSearchParams[key]] : []),
  }),
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
    // i18n mock returns key — empty.subtitle
    await waitFor(() =>
      expect(screen.getByText('empty.subtitle')).toBeInTheDocument(),
    );
  });

  it('renders new item button linking to /workspace/acme/items/new', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    const btn = screen.getByRole('link', { name: /newButtonAria/i });
    expect(btn).toHaveAttribute('href', '/workspace/acme/items/new');
  });

  it('renders item title as link to detail page', async () => {
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
    const link = screen.getByRole('link', { name: /implement login flow/i });
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-1');
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
    // aria-label is translated key: 'stateFilterAria'
    expect(screen.getByRole('combobox', { name: /stateFilterAria/i })).toBeInTheDocument();
  });

  // ─── Pagination ───────────────────────────────────────────────────────────────

  it('renders pagination controls when total > page_size', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 45, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );
    // Prev button disabled on page 1 — aria-label is 'pagination.prev'
    expect(screen.getByRole('button', { name: /pagination.prev/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /pagination.next/i })).not.toBeDisabled();
  });

  it('Next button advances page and calls replace with updated search params', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 45, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );

    const nextBtn = screen.getByRole('button', { name: /pagination.next/i });
    await userEvent.click(nextBtn);

    expect(mockReplace).toHaveBeenCalled();
    const calls = mockReplace.mock.calls;
    const lastCall = calls[calls.length - 1]?.[0] as string | undefined;
    expect(lastCall).toBeDefined();
    expect(lastCall).toContain('page=2');
  });

  it('Prev button is disabled on first page', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 45, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: /pagination.prev/i })).toBeDisabled();
  });

  it('Next button is disabled on last page', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 20, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: /pagination.next/i })).toBeDisabled();
  });

  it('does not render pagination controls when total <= page_size', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('empty.subtitle')).toBeInTheDocument(),
    );
    expect(screen.queryByRole('button', { name: /pagination.prev/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /pagination.next/i })).toBeNull();
  });

  // ─── URL-sync state filter ─────────────────────────────────────────────────

  it('pre-selects state filter from URL ?state=in_review', async () => {
    mockSearchParams = { state: 'in_review' };
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
    const select = screen.getByRole('combobox', { name: /stateFilterAria/i });
    expect((select as HTMLSelectElement).value).toBe('in_review');
    mockSearchParams = {};
  });

  it('changing state filter calls router.replace with ?state= and resets page to 1', async () => {
    mockReplace.mockClear();
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 45, page: 1, page_size: 20 },
        }),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Implement login flow')).toBeInTheDocument(),
    );

    const select = screen.getByRole('combobox', { name: /stateFilterAria/i });
    await userEvent.selectOptions(select, 'draft');

    const replaceCalls = mockReplace.mock.calls.map((c) => c[0] as string);
    const stateCall = replaceCalls.find((u) => u.includes('state=draft'));
    expect(stateCall).toBeDefined();
    expect(stateCall).toContain('page=1');
  });

  // ─── Error state ─────────────────────────────────────────────────────────────

  it('shows error alert with retry button on 5xx', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json(
          { error: { code: 'SERVER_ERROR', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('selecting "all states" removes ?state from URL', async () => {
    mockSearchParams = { state: 'in_review' };
    mockReplace.mockClear();
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

    const select = screen.getByRole('combobox', { name: /stateFilterAria/i });
    await userEvent.selectOptions(select, '');

    const replaceCalls = mockReplace.mock.calls.map((c) => c[0] as string);
    const noStateCall = replaceCalls.find((u) => !u.includes('state='));
    expect(noStateCall).toBeDefined();
    mockSearchParams = {};
  });
});
