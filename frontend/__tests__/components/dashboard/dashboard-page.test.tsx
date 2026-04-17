/**
 * EP-09 — DashboardPage integration tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import DashboardPage from '@/app/workspace/[slug]/dashboard/page';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const mockDashboard = {
  work_items: {
    total: 25,
    by_state: { draft: 10, in_review: 10, ready: 5 },
    by_type: { bug: 8, task: 17 },
    avg_completeness: 72.4,
  },
  recent_activity: [
    {
      work_item_id: 'wi-1',
      title: 'Critical bug fix',
      event_type: 'state_changed',
      actor_id: 'u-1',
      actor_name: 'Ada Lovelace',
      occurred_at: '2026-04-15T10:00:00Z',
    },
  ],
};

function stubDashboard(data = mockDashboard) {
  server.use(
    http.get('http://localhost/api/v1/workspaces/dashboard', () =>
      HttpResponse.json({ data, message: 'ok' }),
    ),
  );
}

describe('DashboardPage', () => {
  it('shows skeleton while loading', () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    expect(screen.getByTestId('dashboard-skeleton')).toBeInTheDocument();
  });

  it('renders summary cards after load', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByTestId('summary-total')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('summary-total')).toHaveTextContent('25');
  });

  it('renders avg completeness', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByTestId('summary-avg-completeness')).toBeInTheDocument(),
    );
    // 72.4 rounded = 72
    expect(screen.getByTestId('summary-avg-completeness')).toHaveTextContent('72%');
  });

  it('renders state distribution bar', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByTestId('state-distribution-bar')).toBeInTheDocument(),
    );
  });

  it('renders type distribution bar', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByTestId('type-distribution-bar')).toBeInTheDocument(),
    );
  });

  it('renders recent activity items', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Critical bug fix')).toBeInTheDocument(),
    );
  });

  it('activity item links to detail page', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByText('Critical bug fix')).toBeInTheDocument(),
    );
    const link = screen.getByText('Critical bug fix').closest('a');
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-1');
  });

  it('shows error state on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/workspaces/dashboard', () =>
        HttpResponse.json({ error: { message: 'Server error' } }, { status: 500 }),
      ),
    );
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument(),
    );
  });

  it('refresh button triggers data re-fetch', async () => {
    stubDashboard();
    render(<DashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() =>
      expect(screen.getByTestId('summary-total')).toBeInTheDocument(),
    );

    let fetchCount = 0;
    server.use(
      http.get('http://localhost/api/v1/workspaces/dashboard', () => {
        fetchCount++;
        return HttpResponse.json({ data: mockDashboard, message: 'ok' });
      }),
    );

    const refreshBtn = screen.getByRole('button', { name: 'retry' });
    await userEvent.click(refreshBtn);

    await waitFor(() => expect(fetchCount).toBeGreaterThan(0));
  });
});
