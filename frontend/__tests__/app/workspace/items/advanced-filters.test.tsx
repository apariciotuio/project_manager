/**
 * EP-09 — Advanced filters on items page.
 * Tests URL-synced multi-select state/type, priority, completeness slider, date range, reset.
 * i18n mock: useTranslations() => (key) => key — labels equal the key without namespace prefix.
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

const mockItem: WorkItemResponse = {
  id: 'wi-1',
  title: 'Test item',
  type: 'task',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: null,
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 50,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-15T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

function stubWorkItems(items = [mockItem], total = items.length) {
  server.use(
    http.get('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({ data: { items, total, page: 1, page_size: 20 } }),
    ),
  );
}

beforeEach(() => {
  mockSearchParams = {};
  mockReplace.mockClear();
  mockPush.mockClear();
});

// The mock useTranslations returns just the leaf key without namespace prefix.
// So tFilters('typeFilterAria') === 'typeFilterAria'.

describe('WorkItemsPage — advanced filters', () => {
  it('renders type filter dropdown', async () => {
    stubWorkItems([]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByTestId('work-items-skeleton')).toBeNull());
    expect(screen.getByRole('combobox', { name: 'typeFilterAria' })).toBeInTheDocument();
  });

  it('renders priority filter dropdown', async () => {
    stubWorkItems([]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByTestId('work-items-skeleton')).toBeNull());
    expect(screen.getByRole('combobox', { name: 'priorityFilterAria' })).toBeInTheDocument();
  });

  it('renders completeness min range slider', async () => {
    stubWorkItems([]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByTestId('work-items-skeleton')).toBeNull());
    expect(screen.getByRole('slider', { name: 'completenessAria' })).toBeInTheDocument();
  });

  it('renders date-from and date-to inputs', async () => {
    stubWorkItems([]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByTestId('work-items-skeleton')).toBeNull());
    // labels use tFilters('dateFrom') → 'dateFrom', tFilters('dateTo') → 'dateTo'
    expect(screen.getByLabelText('dateFrom')).toBeInTheDocument();
    expect(screen.getByLabelText('dateTo')).toBeInTheDocument();
  });

  it('renders Reset filters button', async () => {
    stubWorkItems([]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.queryByTestId('work-items-skeleton')).toBeNull());
    expect(screen.getByRole('button', { name: 'resetAria' })).toBeInTheDocument();
  });

  it('selecting type filter calls router.replace with ?type=bug', async () => {
    stubWorkItems([mockItem]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.getByText('Test item')).toBeInTheDocument());

    const typeSelect = screen.getByRole('combobox', { name: 'typeFilterAria' });
    await userEvent.selectOptions(typeSelect, 'bug');

    const calls = mockReplace.mock.calls.map((c) => c[0] as string);
    expect(calls.some((u) => u.includes('type=bug'))).toBe(true);
  });

  it('selecting priority filter calls router.replace with ?priority=high', async () => {
    stubWorkItems([mockItem]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.getByText('Test item')).toBeInTheDocument());

    const prioritySelect = screen.getByRole('combobox', { name: 'priorityFilterAria' });
    await userEvent.selectOptions(prioritySelect, 'high');

    const calls = mockReplace.mock.calls.map((c) => c[0] as string);
    expect(calls.some((u) => u.includes('priority=high'))).toBe(true);
  });

  it('reset button clears all filters and calls router.replace without filter params', async () => {
    mockSearchParams = { state: 'draft', type: 'bug', priority: 'high' };
    stubWorkItems([mockItem]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.getByText('Test item')).toBeInTheDocument());

    mockReplace.mockClear();
    const resetBtn = screen.getByRole('button', { name: 'resetAria' });
    await userEvent.click(resetBtn);

    const calls = mockReplace.mock.calls.map((c) => c[0] as string);
    const lastCall = calls[calls.length - 1] ?? '';
    expect(lastCall).not.toContain('state=');
    expect(lastCall).not.toContain('type=');
    expect(lastCall).not.toContain('priority=');
  });

  it('pre-selects type filter from URL ?type=bug', async () => {
    mockSearchParams = { type: 'bug' };
    stubWorkItems([mockItem]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.getByText('Test item')).toBeInTheDocument());
    const typeSelect = screen.getByRole('combobox', { name: 'typeFilterAria' }) as HTMLSelectElement;
    expect(typeSelect.value).toBe('bug');
  });

  it('pre-selects priority filter from URL ?priority=critical', async () => {
    mockSearchParams = { priority: 'critical' };
    stubWorkItems([mockItem]);
    render(<WorkItemsPage params={{ slug: 'acme' }} />);
    await waitFor(() => expect(screen.getByText('Test item')).toBeInTheDocument());
    const prioritySelect = screen.getByRole('combobox', { name: 'priorityFilterAria' }) as HTMLSelectElement;
    expect(prioritySelect.value).toBe('critical');
  });
});
