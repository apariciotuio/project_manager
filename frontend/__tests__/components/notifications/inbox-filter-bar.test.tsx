import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

// URL state mock — capture router.replace calls
const mockReplace = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => mockSearchParams,
  useParams: () => ({ slug: 'acme' }),
}));

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const makeNotification = (overrides: Record<string, unknown> = {}) => ({
  id: 'n1',
  workspace_id: 'ws1',
  recipient_id: 'u1',
  type: 'mention',
  state: 'unread',
  actor_id: 'actor1',
  subject_type: 'work_item',
  subject_id: 'wi1',
  deeplink: '/workspace/acme/items/wi1',
  quick_action: null,
  extra: { summary: 'Alice mentioned you', actor_name: 'Alice' },
  created_at: '2026-04-16T10:00:00Z',
  read_at: null,
  actioned_at: null,
  ...overrides,
});

describe('InboxFilterBar', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    // Reset search params
    Array.from(mockSearchParams.keys()).forEach((k) => mockSearchParams.delete(k));
  });

  it('renders all filter tabs (All / Unread / Mentions / Reviews) and search input', async () => {
    const { InboxFilterBar } = await import('@/components/notifications/inbox-filter-bar');
    render(
      <InboxFilterBar
        activeFilter="all"
        onFilterChange={vi.fn()}
        search=""
        onSearchChange={vi.fn()}
      />,
    );

    expect(screen.getByRole('tab', { name: /workspace\.inbox\.filter\.all/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /workspace\.inbox\.filter\.unread/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /workspace\.inbox\.filter\.mentions/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /workspace\.inbox\.filter\.reviews/i })).toBeTruthy();
    expect(screen.getByRole('searchbox')).toBeTruthy();
  });

  it('calls onFilterChange when a tab is clicked', async () => {
    const onFilterChange = vi.fn();
    const { InboxFilterBar } = await import('@/components/notifications/inbox-filter-bar');
    render(
      <InboxFilterBar
        activeFilter="all"
        onFilterChange={onFilterChange}
        search=""
        onSearchChange={vi.fn()}
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole('tab', { name: /workspace\.inbox\.filter\.unread/i }));
    expect(onFilterChange).toHaveBeenCalledWith('unread');
  });

  it('calls onSearchChange when typing in the search input', async () => {
    const onSearchChange = vi.fn();
    const { InboxFilterBar } = await import('@/components/notifications/inbox-filter-bar');
    render(
      <InboxFilterBar
        activeFilter="all"
        onFilterChange={vi.fn()}
        search=""
        onSearchChange={onSearchChange}
      />,
    );

    const user = userEvent.setup();
    await user.type(screen.getByRole('searchbox'), 'A');
    expect(onSearchChange).toHaveBeenCalledWith('A');
  });

  it('URL-syncs filter — router.replace called with ?filter=unread on tab change', async () => {
    const { InboxFilterBarWithUrlSync } = await import(
      '@/components/notifications/inbox-filter-bar'
    );
    render(<InboxFilterBarWithUrlSync />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('tab', { name: /workspace\.inbox\.filter\.unread/i }));

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalled();
      const call = (mockReplace.mock.calls[0] as [string])[0];
      expect(call).toContain('filter=unread');
    });
  });

  it('passes only_unread=true to listNotifications when "Unread" tab is active (filter=unread in URL)', async () => {
    let capturedUrl = '';
    // Set searchParams to have filter=unread
    mockSearchParams.set('filter', 'unread');

    server.use(
      http.get('http://localhost/api/v1/notifications', ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        });
      }),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } }),
      ),
    );

    vi.doMock('@/app/providers/auth-provider', () => ({
      useAuth: () => ({
        user: {
          id: 'u1',
          full_name: 'Ada',
          workspace_id: 'ws1',
          workspace_slug: 'acme',
          email: 'a@b.com',
          avatar_url: null,
          is_superadmin: false,
        },
        isLoading: false,
        isAuthenticated: true,
        logout: vi.fn(),
      }),
    }));

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    const { unmount } = render(<InboxPage params={{ slug: 'acme' }} />);

    await waitFor(() => expect(capturedUrl).toBeTruthy());
    expect(capturedUrl).toContain('only_unread=true');

    unmount();
    mockSearchParams.delete('filter');
  });
});
