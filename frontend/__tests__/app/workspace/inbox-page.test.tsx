import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

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

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    const str = `${ns}.${key}`;
    if (!params) return str;
    return Object.entries(params).reduce(
      (s, [k, v]) => s.replace(`{${k}}`, String(v)),
      str,
    );
  },
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

const mockV2Notifications = [
  makeNotification({ id: 'n1', state: 'unread' }),
  makeNotification({
    id: 'n2',
    type: 'assignment',
    state: 'read',
    extra: { summary: 'Bob assigned you a task', actor_name: 'Bob' },
    deeplink: null,
  }),
];

describe('InboxPage', () => {
  it('renders notification summaries', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: mockV2Notifications, total: 2, page: 1, page_size: 20 } })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 1 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    expect(await screen.findByText('Alice mentioned you')).toBeTruthy();
    expect(await screen.findByText('Bob assigned you a task')).toBeTruthy();
  });

  it('shows empty state when no notifications', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 20 } })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    expect(await screen.findByText(/workspace\.inbox\.empty/i)).toBeTruthy();
  });

  it('unread notification has visual indicator', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: mockV2Notifications, total: 2, page: 1, page_size: 20 } })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 1 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    await screen.findByText('Alice mentioned you');
    const unreadIndicator = screen.getByLabelText('Unread');
    expect(unreadIndicator).toBeTruthy();
  });

  it('clicking notification marks it read and navigates if deeplink exists', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: mockV2Notifications, total: 2, page: 1, page_size: 20 } })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 1 } })
      ),
      http.patch('http://localhost/api/v1/notifications/n1/read', () =>
        HttpResponse.json({ data: { ...mockV2Notifications[0], state: 'read', read_at: new Date().toISOString() } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    const item = await screen.findByText('Alice mentioned you');
    await userEvent.click(item);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/workspace/acme/items/wi1');
    });
  });

  it('shows mark-all-read button', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: mockV2Notifications, total: 2, page: 1, page_size: 20 } })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 1 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    await screen.findByText('Alice mentioned you');
    expect(screen.getByRole('button', { name: /workspace\.inbox\.markAllRead/i })).toBeTruthy();
  });

  it('shows unread-only toggle filter', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: mockV2Notifications, total: 2, page: 1, page_size: 20 } })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 1 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    await screen.findByText('Alice mentioned you');
    // Filter checkbox or button should be visible
    const filter = screen.getByRole('checkbox', { name: /workspace\.inbox\.onlyUnread/i });
    expect(filter).toBeTruthy();
  });

  it('shows loading skeleton while fetching', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', async () => {
        await new Promise(() => {});
        return HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 20 } });
      }),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    // Skeleton should be visible immediately
    expect(document.querySelector('[data-skeleton]')).toBeTruthy();
  });

  it('shows error banner on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'oops' } }, { status: 500 })
      ),
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });
});
