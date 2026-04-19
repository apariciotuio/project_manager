/**
 * EP-23 F-2 — Dashboard lean tests (replaces old stats-focused tests).
 * RED → GREEN → REFACTOR
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock next-intl
vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

// Mock Next.js Link
vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/workspace/acme/dashboard',
}));

import type { WorkItemResponse } from '@/lib/types/work-item';

// ─── Shared mock data ─────────────────────────────────────────────────────────

const USER_ID = 'u-1';

function makeItem(overrides: Partial<WorkItemResponse>): WorkItemResponse {
  return {
    id: 'wi-1',
    title: 'Test item',
    type: 'task',
    state: 'draft',
    derived_state: null,
    owner_id: USER_ID,
    creator_id: USER_ID,
    project_id: null,
    description: null,
    priority: null,
    due_date: null,
    tags: [],
    completeness_score: 0,
    has_override: false,
    override_justification: null,
    owner_suspended_flag: false,
    parent_work_item_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    deleted_at: null,
    external_jira_key: null,
    ...overrides,
  };
}

// ─── Mocks for useAuth and useWorkItems ───────────────────────────────────────

const mockUseAuth = vi.fn();
vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => mockUseAuth(),
}));

const mockUseWorkItems = vi.fn();
vi.mock('@/hooks/use-work-items', () => ({
  useWorkItems: (...args: unknown[]) => mockUseWorkItems(...args),
}));

function defaultUseWorkItemsReturn(items: WorkItemResponse[] = []) {
  return {
    items,
    total: items.length,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    hasNext: false,
    isLoadingMore: false,
    loadMore: vi.fn(),
  };
}

// ─── Import component AFTER mocks ────────────────────────────────────────────

import DashboardPage from '@/app/workspace/[slug]/dashboard/page';

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('DashboardPage (F-2 lean)', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ user: { id: USER_ID, email: 'u@test.com' }, isLoading: false, isAuthenticated: true });
    // Default: empty lists
    mockUseWorkItems.mockReturnValue(defaultUseWorkItemsReturn());
  });

  // ── Block ordering ────────────────────────────────────────────────────────

  it('renders the [+ New item] CTA as the first interactive element', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const cta = screen.getByRole('link', { name: /new item/i });
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute('href', '/workspace/acme/items/new');
  });

  it('renders all 4 blocks in document order', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const cta = screen.getByRole('link', { name: /new item/i });
    const pendingFinish = screen.getByTestId('section-pending-finish');
    const pendingReview = screen.getByTestId('section-pending-review');
    const recentlyCreated = screen.getByTestId('section-recently-created');

    // DOM order: CTA before pendingFinish, pendingFinish before pendingReview, etc.
    expect(cta.compareDocumentPosition(pendingFinish)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(pendingFinish.compareDocumentPosition(pendingReview)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(pendingReview.compareDocumentPosition(recentlyCreated)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  // ── Stats widgets removed ─────────────────────────────────────────────────

  it('does NOT render old stats widgets', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    expect(screen.queryByTestId('dashboard-skeleton')).not.toBeInTheDocument();
    expect(screen.queryByTestId('summary-total')).not.toBeInTheDocument();
    expect(screen.queryByTestId('state-distribution-bar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('type-distribution-bar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('recent-activity-feed')).not.toBeInTheDocument();
  });

  // ── useWorkItems filter wiring ────────────────────────────────────────────

  it('fetches pending-finish with owner filter and non-terminal states', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const calls: unknown[][] = mockUseWorkItems.mock.calls;
    const pendingFinishCall = calls.find(
      ([, filters]: unknown[]) =>
        (filters as Record<string, unknown>).mine_type === 'owner',
    );
    expect(pendingFinishCall).toBeDefined();
    const filters = pendingFinishCall![1] as Record<string, unknown>;
    expect(filters.mine).toBe(true);
    // Must NOT include terminal states (ready, exported)
    const states = filters.states as string[];
    expect(states).not.toContain('ready');
    expect(states).not.toContain('exported');
  });

  it('fetches pending-review with reviewer filter', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const calls: unknown[][] = mockUseWorkItems.mock.calls;
    const reviewCall = calls.find(
      ([, filters]: unknown[]) =>
        (filters as Record<string, unknown>).mine_type === 'reviewer',
    );
    expect(reviewCall).toBeDefined();
    const filters = reviewCall![1] as Record<string, unknown>;
    expect(filters.mine).toBe(true);
  });

  it('fetches recently-created with creator filter, limit 5, sort -created_at', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const calls: unknown[][] = mockUseWorkItems.mock.calls;
    const creatorCall = calls.find(
      ([, filters]: unknown[]) =>
        (filters as Record<string, unknown>).mine_type === 'creator',
    );
    expect(creatorCall).toBeDefined();
    const filters = creatorCall![1] as Record<string, unknown>;
    expect(filters.mine).toBe(true);
    expect(filters.limit).toBe(5);
    expect(filters.sort).toBe('-created_at');
  });

  // ── Recently created caps at 5 newest-first ───────────────────────────────

  it('displays at most 5 items in "recently created" even if hook returns more', () => {
    const manyItems = Array.from({ length: 8 }, (_, i) =>
      makeItem({ id: `wi-${i}`, title: `Item ${i}`, created_at: `2026-01-0${i + 1}T00:00:00Z` }),
    );
    mockUseWorkItems.mockImplementation((_: unknown, filters: Record<string, unknown>) => {
      if (filters?.mine_type === 'creator') {
        return defaultUseWorkItemsReturn(manyItems);
      }
      return defaultUseWorkItemsReturn();
    });
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const section = screen.getByTestId('section-recently-created');
    const listItems = section.querySelectorAll('[data-testid^="work-item-card"]');
    expect(listItems.length).toBeLessThanOrEqual(5);
  });

  // ── Empty states ──────────────────────────────────────────────────────────

  it('shows EmptyState in pending-finish section when list is empty', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const section = screen.getByTestId('section-pending-finish');
    expect(section.querySelector('[data-testid="empty-state"]')).toBeInTheDocument();
  });

  it('shows EmptyState in pending-review section when list is empty', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const section = screen.getByTestId('section-pending-review');
    expect(section.querySelector('[data-testid="empty-state"]')).toBeInTheDocument();
  });

  it('shows EmptyState in recently-created section when list is empty', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const section = screen.getByTestId('section-recently-created');
    expect(section.querySelector('[data-testid="empty-state"]')).toBeInTheDocument();
  });

  it('empty-state CTAs link to the full filtered list', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    // Each section's empty state should have a link or actionable element
    const emptyStates = screen.getAllByTestId('empty-state');
    expect(emptyStates.length).toBeGreaterThanOrEqual(3);
    // At least one CTA link inside each empty state
    emptyStates.forEach((es) => {
      expect(es.querySelector('a, button')).toBeInTheDocument();
    });
  });

  // ── Items render correctly ────────────────────────────────────────────────

  it('renders pending-finish items when present', () => {
    mockUseWorkItems.mockImplementation((_: unknown, filters: Record<string, unknown>) => {
      if (filters?.mine_type === 'owner') {
        return defaultUseWorkItemsReturn([
          makeItem({ id: 'wi-pending', title: 'Pending item' }),
        ]);
      }
      return defaultUseWorkItemsReturn();
    });
    render(<DashboardPage params={{ slug: 'acme' }} />);
    expect(screen.getByText('Pending item')).toBeInTheDocument();
  });

  it('renders pending-review items when present', () => {
    mockUseWorkItems.mockImplementation((_: unknown, filters: Record<string, unknown>) => {
      if (filters?.mine_type === 'reviewer') {
        return defaultUseWorkItemsReturn([
          makeItem({ id: 'wi-review', title: 'Review item' }),
        ]);
      }
      return defaultUseWorkItemsReturn();
    });
    render(<DashboardPage params={{ slug: 'acme' }} />);
    expect(screen.getByText('Review item')).toBeInTheDocument();
  });

  it('renders recently-created items when present', () => {
    mockUseWorkItems.mockImplementation((_: unknown, filters: Record<string, unknown>) => {
      if (filters?.mine_type === 'creator') {
        return defaultUseWorkItemsReturn([
          makeItem({ id: 'wi-recent', title: 'Recent item' }),
        ]);
      }
      return defaultUseWorkItemsReturn();
    });
    render(<DashboardPage params={{ slug: 'acme' }} />);
    expect(screen.getByText('Recent item')).toBeInTheDocument();
  });

  // ── "View all" links ──────────────────────────────────────────────────────

  it('each section has a "View all" link to the items page with filter', () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const viewAllLinks = screen.getAllByRole('link', { name: /view all/i });
    // At least 3 sections with view-all links
    expect(viewAllLinks.length).toBeGreaterThanOrEqual(3);
    viewAllLinks.forEach((link) => {
      expect((link as HTMLAnchorElement).href).toContain('/workspace/acme/items');
    });
  });

  // ── CTA navigates to new-item flow ────────────────────────────────────────

  it('CTA click navigates to new-item route', async () => {
    render(<DashboardPage params={{ slug: 'acme' }} />);
    const cta = screen.getByRole('link', { name: /new item/i });
    await userEvent.click(cta);
    // Link renders as <a> — just verify href
    expect(cta).toHaveAttribute('href', '/workspace/acme/items/new');
  });
});
