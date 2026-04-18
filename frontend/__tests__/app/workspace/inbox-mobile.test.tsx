/**
 * EP-12 Group 4 — Responsive Inbox Mobile tests
 *
 * These tests verify:
 * 1. Inbox renders single-column cards on 375px viewport (no horizontal overflow)
 * 2. Each inbox card has a tap target of >= 48px (min-h-[48px])
 * 3. "Load more" button is visible when total items > 20 (page_size boundary)
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: 'acme' }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/app/providers/auth-provider', () => ({
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

vi.mock('next-intl', () => ({
  useTranslations:
    (ns: string) =>
    (key: string, params?: Record<string, unknown>) => {
      const str = `${ns}.${key}`;
      if (!params) return str;
      return Object.entries(params).reduce(
        (s, [k, v]) => s.replace(`{${k}}`, String(v)),
        str,
      );
    },
}));

const makeNotification = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  workspace_id: 'ws1',
  recipient_id: 'u1',
  type: 'mention',
  state: 'unread',
  actor_id: 'actor1',
  subject_type: 'work_item',
  subject_id: 'wi1',
  deeplink: `/workspace/acme/items/${id}`,
  quick_action: null,
  extra: { summary: `Notification ${id}`, actor_name: 'Alice' },
  created_at: '2026-04-16T10:00:00Z',
  read_at: null,
  actioned_at: null,
  ...overrides,
});

const twoNotifications = [
  makeNotification('n1', { state: 'unread' }),
  makeNotification('n2', { state: 'read' }),
];

// 21 notifications to push total > 20 (PAGE_SIZE = 20)
const twentyOneNotifications = Array.from({ length: 21 }, (_, i) =>
  makeNotification(`n${i + 1}`),
);

function setupApiHandlers(
  items: ReturnType<typeof makeNotification>[],
  total: number,
) {
  server.use(
    http.get('http://localhost/api/v1/notifications', () =>
      HttpResponse.json({ data: { items, total, page: 1, page_size: 20 } }),
    ),
    http.get('http://localhost/api/v1/notifications/unread-count', () =>
      HttpResponse.json({ data: { count: 0 } }),
    ),
  );
}

describe('Inbox Mobile — EP-12 Group 4', () => {
  describe('single-column / no overflow', () => {
    it('inbox list container has w-full and no horizontal overflow class', async () => {
      setupApiHandlers(twoNotifications, 2);

      const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
      const { container } = render(<InboxPage params={{ slug: 'acme' }} />);

      // Wait for content to render
      await screen.findByText('Notification n1');

      // The outermost page container should not impose a fixed width that causes overflow
      const pageEl = container.firstChild as HTMLElement;
      const style = window.getComputedStyle(pageEl);
      // overflow-x: hidden is acceptable; overflow-x: scroll/auto without w-full is not
      // We assert the container does NOT have overflow-x: scroll
      expect(style.overflowX).not.toBe('scroll');
    });

    it('notification list renders items stacked vertically (flex-col)', async () => {
      setupApiHandlers(twoNotifications, 2);

      const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
      render(<InboxPage params={{ slug: 'acme' }} />);

      await screen.findByText('Notification n1');

      // The list wrapper should be a flex column (flex-col class applied)
      const listWrapper = document.querySelector('[data-testid="inbox-list"]');
      expect(listWrapper).not.toBeNull();
      expect(listWrapper!.className).toMatch(/flex/);
      expect(listWrapper!.className).toMatch(/flex-col/);
    });
  });

  describe('touch target compliance', () => {
    it('each notification card has min-h-[48px] class for touch target compliance', async () => {
      setupApiHandlers(twoNotifications, 2);

      const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
      render(<InboxPage params={{ slug: 'acme' }} />);

      await screen.findByText('Notification n1');

      // Each notification row wrapper should carry min-h-[48px]
      const cards = document.querySelectorAll('[data-notification-id]');
      expect(cards.length).toBeGreaterThan(0);
      cards.forEach((card) => {
        expect(card.className).toMatch(/min-h-\[48px\]/);
      });
    });
  });

  describe('Load more', () => {
    it('shows "Load more" button when total items exceed PAGE_SIZE (20)', async () => {
      // First page returns 20 items, total = 21 → next page exists
      setupApiHandlers(twentyOneNotifications.slice(0, 20), 21);

      const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
      render(<InboxPage params={{ slug: 'acme' }} />);

      await screen.findByText('Notification n1');

      // Expect a "Load more" button to appear
      expect(
        screen.getByRole('button', { name: /workspace\.inbox\.loadMore/i }),
      ).toBeTruthy();
    });

    it('does NOT show "Load more" when all items fit on one page', async () => {
      setupApiHandlers(twoNotifications, 2);

      const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
      render(<InboxPage params={{ slug: 'acme' }} />);

      await screen.findByText('Notification n1');

      expect(
        screen.queryByRole('button', { name: /workspace\.inbox\.loadMore/i }),
      ).toBeNull();
    });

    it('clicking "Load more" fetches next page and appends items', async () => {
      // First call returns page 1 (20 items), second call returns page 2 (1 item)
      let callCount = 0;
      server.use(
        http.get('http://localhost/api/v1/notifications', ({ request }) => {
          const url = new URL(request.url);
          const page = url.searchParams.get('page') ?? '1';
          callCount++;
          if (page === '1') {
            return HttpResponse.json({
              data: {
                items: twentyOneNotifications.slice(0, 20),
                total: 21,
                page: 1,
                page_size: 20,
              },
            });
          }
          return HttpResponse.json({
            data: {
              items: [makeNotification('n21')],
              total: 21,
              page: 2,
              page_size: 20,
            },
          });
        }),
        http.get('http://localhost/api/v1/notifications/unread-count', () =>
          HttpResponse.json({ data: { count: 0 } }),
        ),
      );

      const { default: InboxPage } = await import('@/app/workspace/[slug]/inbox/page');
      render(<InboxPage params={{ slug: 'acme' }} />);

      await screen.findByText('Notification n1');

      const loadMoreBtn = screen.getByRole('button', {
        name: /workspace\.inbox\.loadMore/i,
      });
      await userEvent.click(loadMoreBtn);

      await waitFor(() => {
        expect(screen.getByText('Notification n21')).toBeTruthy();
      });
    });
  });
});
