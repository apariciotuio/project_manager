/**
 * EP-09 — Load more button on items list page.
 * Tests: "Load more" button appears when has_next=true, appends items on click, hidden when has_next=false.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../../msw/server';
import WorkItemsPage from '@/app/workspace/[slug]/items/page';
import type { WorkItemResponse } from '@/lib/types/work-item';

const mockReplace = vi.fn();
let mockSearchParams: Record<string, string> = {};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace }),
  usePathname: () => '/workspace/acme/items',
  useParams: () => ({ slug: 'acme' }),
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams[key] ?? null,
    getAll: (key: string) => (mockSearchParams[key] ? [mockSearchParams[key]] : []),
  }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}(${JSON.stringify(params)})`;
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

vi.mock('@/components/search/search-bar', () => ({
  SearchBar: () => null,
}));
vi.mock('@/components/search/saved-searches-menu', () => ({
  SavedSearchesMenu: () => null,
}));
vi.mock('@/components/hierarchy/ParentPicker', () => ({
  ParentPicker: () => null,
}));

const makeItem = (id: string): WorkItemResponse => ({
  id,
  title: `Item ${id}`,
  type: 'task',
  state: 'draft',
  priority: 'medium',
  completeness_score: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  workspace_id: 'ws-1',
  project_id: 'p-1',
  owner_id: null,
  parent_work_item_id: null,
  description: null,
  jira_key: null,
  jira_url: null,
  days_in_state: 1,
  is_overridden: false,
  tags: [],
  depth: 0,
});

const PAGE1_ITEMS = [makeItem('wi-1'), makeItem('wi-2')];
const PAGE2_ITEMS = [makeItem('wi-3')];

function setupPagedHandler(hasNext: boolean, cursor: string | null = null) {
  server.use(
    http.get('*/api/v1/work-items', ({ request }) => {
      const url = new URL(request.url);
      const incomingCursor = url.searchParams.get('cursor');
      if (incomingCursor === 'cur-next') {
        return HttpResponse.json({
          data: { items: PAGE2_ITEMS, total: 3, page: 2, page_size: 20 },
        });
      }
      return HttpResponse.json({
        data: {
          items: PAGE1_ITEMS,
          total: 3,
          page: 1,
          page_size: 20,
          // cursor fields piggy-backed in response for EP-09
          cursor: cursor,
          has_next: hasNext,
        },
      });
    }),
  );
}

beforeEach(() => {
  mockReplace.mockReset();
  mockSearchParams = {};
  server.resetHandlers();
});

describe('Items page — Load more', () => {
  it('shows "Load more" button when has_next is true', async () => {
    setupPagedHandler(true, 'cur-next');
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByText('Item wi-1')).toBeTruthy());
    expect(screen.getByRole('button', { name: /load more/i })).toBeDefined();
  });

  it('does not show "Load more" when has_next is false', async () => {
    setupPagedHandler(false, null);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByText('Item wi-1')).toBeTruthy());
    expect(screen.queryByRole('button', { name: /load more/i })).toBeNull();
  });

  it('appends next page items on "Load more" click without replacing existing', async () => {
    setupPagedHandler(true, 'cur-next');
    // Second call (with cursor) returns PAGE2_ITEMS without has_next
    server.use(
      http.get('*/api/v1/work-items', ({ request }) => {
        const url = new URL(request.url);
        const incomingCursor = url.searchParams.get('cursor');
        if (incomingCursor === 'cur-next') {
          return HttpResponse.json({
            data: { items: PAGE2_ITEMS, total: 3, page: 2, page_size: 20, cursor: null, has_next: false },
          });
        }
        return HttpResponse.json({
          data: { items: PAGE1_ITEMS, total: 3, page: 1, page_size: 20, cursor: 'cur-next', has_next: true },
        });
      }),
    );

    const user = userEvent.setup();
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByText('Item wi-1')).toBeTruthy());

    const loadMore = screen.getByRole('button', { name: /load more/i });
    await user.click(loadMore);

    await waitFor(() => expect(screen.queryByText('Item wi-3')).toBeTruthy());
    // Original items still present
    expect(screen.queryByText('Item wi-1')).toBeTruthy();
    expect(screen.queryByText('Item wi-2')).toBeTruthy();
    // Load more gone after last page
    expect(screen.queryByRole('button', { name: /load more/i })).toBeNull();
  });
});
