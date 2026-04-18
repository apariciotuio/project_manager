/**
 * Group 5 — Responsive: Work Item Detail Mobile
 *
 * Tests:
 * 1. Metadata accordion present on < 640px viewport
 * 2. Action bar (StickyActionBar) is sticky at bottom on mobile
 * 3. No horizontal overflow on 375px viewport
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import WorkItemDetailPage from '@/app/workspace/[slug]/items/[id]/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      full_name: 'Ada Lovelace',
      workspace_id: 'ws1',
      workspace_slug: 'acme',
      email: 'ada@co.com',
      avatar_url: null,
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

const WORK_ITEM = {
  id: 'wi-1',
  title: 'Fix login bug',
  type: 'bug',
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
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
};

function setupHandlers() {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1', () =>
      HttpResponse.json({ data: WORK_ITEM }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/completeness', () =>
      HttpResponse.json({ data: { score: 45, level: 'medium', dimensions: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/gaps', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/next-step', () =>
      HttpResponse.json({
        data: {
          next_step: 'improve_content',
          message: 'Fill in sections.',
          blocking: false,
          gaps_referenced: [],
          suggested_validators: [],
        },
      }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/locks', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/task-tree', () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', tree: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/reviews', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
      HttpResponse.json({ data: { events: [], next_cursor: null } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/tags', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] })),
    http.get('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } }),
    ),
  );
}

describe('WorkItemDetailPage — mobile responsive (Group 5)', () => {
  it('[RED] metadata accordion is present on mobile viewport (< 640px)', async () => {
    // jsdom doesn't do real media queries, but we verify the accordion element
    // is rendered (visible on mobile, collapsible). On < 640px it should show
    // a collapsible metadata section via data-testid="metadata-accordion".
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));

    expect(screen.getByTestId('metadata-accordion')).toBeInTheDocument();
  });

  it('[RED] sticky action bar renders with data-testid="sticky-action-bar"', async () => {
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));

    // StickyActionBar must be present — it is `fixed bottom-0` on mobile via CSS
    expect(screen.getByTestId('sticky-action-bar')).toBeInTheDocument();
  });

  it('[RED] page wrapper has overflow-x-hidden to prevent horizontal overflow at 375px', async () => {
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));

    // The outermost wrapper must carry overflow-x-hidden so nothing overflows at 375px
    const wrapper = screen.getByTestId('detail-page-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.className).toMatch(/overflow-x-hidden/);
  });
});
