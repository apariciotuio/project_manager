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

const mockNotifications = [
  { id: 'n1', type: 'mention', actor_name: 'Alice', summary: 'Alice mentioned you', deeplink: '/workspace/acme/items/i1', read: false, created_at: '2026-04-16T10:00:00Z' },
  { id: 'n2', type: 'assignment', actor_name: 'Bob', summary: 'Bob assigned you a task', deeplink: null, read: true, created_at: '2026-04-15T09:00:00Z' },
];

describe('InboxPage', () => {
  it('renders notification summaries', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: mockNotifications })
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
        HttpResponse.json({ data: [] })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    expect(await screen.findByText(/no tienes notificaciones/i)).toBeTruthy();
  });

  it('unread notification has visual indicator', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: mockNotifications })
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    await screen.findByText('Alice mentioned you');
    // unread indicator: aria-label or data attribute
    const unreadDot = document.querySelector('[data-unread="true"]');
    expect(unreadDot).toBeTruthy();
  });

  it('clicking notification marks it read and navigates if deeplink exists', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: mockNotifications })
      ),
      http.patch('http://localhost/api/v1/notifications/n1/read', () =>
        HttpResponse.json({})
      )
    );

    const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
    render(<InboxPage params={{ slug: 'acme' }} />);

    const item = await screen.findByText('Alice mentioned you');
    await userEvent.click(item);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/workspace/acme/items/i1');
    });
  });
});
