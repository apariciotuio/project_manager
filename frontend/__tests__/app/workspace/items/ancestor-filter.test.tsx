/**
 * FE-14-10 — Ancestor filter in items list page.
 *
 * Tests:
 * 1. Ancestor filter input is rendered
 * 2. Selecting an ancestor sets ancestor_id in URL
 * 3. Clearing the ancestor filter removes ancestor_id from URL
 * 4. List re-fetches with ancestor_id when filter is applied
 * 5. Breadcrumb banner shows "Showing descendants of: <name>" when ancestor_id is active
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../../msw/server';
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
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
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

const mockItem: WorkItemResponse = {
  id: 'wi-1',
  title: 'Child Story',
  type: 'story',
  state: 'draft',
  derived_state: null,
  owner_id: 'u1',
  creator_id: 'u1',
  project_id: 'p1',
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 0,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: 'epic-1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

const MOCK_ANCESTOR_OPTIONS = {
  items: [
    { id: 'epic-1', title: 'Big Epic', type: 'initiative', state: 'draft' },
  ],
  total: 1,
  cursor: null,
  has_next: false,
};

function setupHandlers() {
  server.use(
    http.get('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({
        data: { items: [mockItem], total: 1, page: 1, page_size: 20 },
      }),
    ),
    // ParentPicker calls /api/v1/projects/:id/work-items
    http.get('http://localhost/api/v1/projects/:projectId/work-items', () =>
      HttpResponse.json({ data: MOCK_ANCESTOR_OPTIONS }),
    ),
  );
}

describe('WorkItemsPage — ancestor filter (FE-14-10)', () => {
  beforeEach(() => {
    mockSearchParams = {};
    mockReplace.mockReset();
  });

  it('renders the ancestor filter combobox', async () => {
    setupHandlers();
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: /ancestor/i })).toBeInTheDocument(),
    );
  });

  it('selecting an ancestor sets ancestor_id in URL via router.replace', async () => {
    setupHandlers();
    render(<WorkItemsPage params={{ slug: 'acme' }} />);

    const input = await screen.findByRole('combobox', { name: /ancestor/i });
    await userEvent.click(input);
    await userEvent.type(input, 'Big');

    const option = await screen.findByText('Big Epic');
    await userEvent.click(option);

    await waitFor(() => {
      const calls = mockReplace.mock.calls.map((c) => c[0] as string);
      expect(calls.some((u) => u.includes('ancestor_id=epic-1'))).toBe(true);
    });
  });

  it('clearing the ancestor filter removes ancestor_id from URL', async () => {
    mockSearchParams = { ancestor_id: 'epic-1' };
    setupHandlers();
    render(<WorkItemsPage params={{ slug: 'acme' }} />);

    // Reset button removes all filters including ancestor_id
    await waitFor(() => screen.getByRole('button', { name: /reset/i }));
    await userEvent.click(screen.getByRole('button', { name: /reset/i }));

    await waitFor(() => {
      const calls = mockReplace.mock.calls.map((c) => c[0] as string);
      expect(calls.some((u) => !u.includes('ancestor_id='))).toBe(true);
    });
  });

  it('re-fetches with ancestor_id when pre-set in URL', async () => {
    mockSearchParams = { ancestor_id: 'epic-1' };
    let capturedUrl = '';
    server.use(
      http.get('http://localhost/api/v1/work-items', ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          data: { items: [mockItem], total: 1, page: 1, page_size: 20 },
        });
      }),
    );
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Child Story')).toBeInTheDocument(),
    );
    expect(capturedUrl).toContain('ancestor_id=epic-1');
  });

  it('shows "Showing descendants of" banner when ancestor_id is active', async () => {
    mockSearchParams = { ancestor_id: 'epic-1' };
    setupHandlers();
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByTestId('ancestor-filter-banner')).toBeInTheDocument(),
    );
  });
});
