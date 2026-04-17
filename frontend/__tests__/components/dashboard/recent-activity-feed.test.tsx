/**
 * EP-09 — RecentActivityFeed component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RecentActivityFeed } from '@/components/dashboard/recent-activity-feed';
import type { DashboardActivityItem } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const mockItem: DashboardActivityItem = {
  work_item_id: 'wi-1',
  title: 'Fix login bug',
  event_type: 'state_changed',
  actor_id: 'user-1',
  actor_name: 'Ada Lovelace',
  occurred_at: '2026-04-15T10:00:00Z',
};

describe('RecentActivityFeed', () => {
  it('renders feed title', () => {
    render(<RecentActivityFeed items={[mockItem]} slug="acme" />);
    expect(screen.getByText('recentActivity.title')).toBeInTheDocument();
  });

  it('renders activity item with title', () => {
    render(<RecentActivityFeed items={[mockItem]} slug="acme" />);
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
  });

  it('activity item links to item detail page', () => {
    render(<RecentActivityFeed items={[mockItem]} slug="acme" />);
    const link = screen.getByText('Fix login bug').closest('a');
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-1');
  });

  it('shows actor name in activity', () => {
    render(<RecentActivityFeed items={[mockItem]} slug="acme" />);
    expect(screen.getByText(/Ada Lovelace/)).toBeInTheDocument();
  });

  it('shows empty state when no activity', () => {
    render(<RecentActivityFeed items={[]} slug="acme" />);
    expect(screen.getByText('recentActivity.empty')).toBeInTheDocument();
    expect(screen.queryByTestId('recent-activity-list')).toBeNull();
  });

  it('renders multiple activity items', () => {
    const items: DashboardActivityItem[] = [
      mockItem,
      {
        ...mockItem,
        work_item_id: 'wi-2',
        title: 'Add feature X',
        occurred_at: '2026-04-14T08:00:00Z',
      },
    ];
    render(<RecentActivityFeed items={items} slug="acme" />);
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    expect(screen.getByText('Add feature X')).toBeInTheDocument();
  });
});
