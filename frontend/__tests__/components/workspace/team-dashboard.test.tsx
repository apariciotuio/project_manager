/**
 * EP-09 — TeamDashboard tests.
 * RED phase: tests written before implementation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import TeamDashboardPage from '@/app/workspace/[slug]/dashboard/team/[teamId]/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/workspace/acme/dashboard/team/team-1',
  useParams: () => ({ slug: 'acme', teamId: 'team-1' }),
  useSearchParams: () => ({ get: () => null, toString: () => '' }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'a@b.com',
      full_name: 'Test User',
      workspace_id: 'ws-1',
      workspace_slug: 'acme',
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
  }),
}));

const mockTeamData = {
  owned_by_state: { draft: 5, in_review: 2, ready: 4 },
  pending_reviews: 3,
  recent_ready_items: 12,
  blocked_count: 1,
};

function setupTeamHandler(data = mockTeamData, status = 200) {
  server.use(
    http.get('http://localhost/api/v1/dashboards/team/:teamId', () =>
      status === 200
        ? HttpResponse.json({ data, message: 'ok' })
        : HttpResponse.json({ error: { message: 'Error', code: 'ERROR', details: {} } }, { status }),
    ),
  );
}

describe('TeamDashboardPage', () => {
  beforeEach(() => {
    setupTeamHandler();
  });

  it('renders loading state initially', () => {
    render(<TeamDashboardPage params={{ slug: 'acme', teamId: 'team-1' }} />);
    expect(screen.getByTestId('team-dashboard-skeleton')).toBeInTheDocument();
  });

  it('renders recent_ready_items card (not velocity)', async () => {
    render(<TeamDashboardPage params={{ slug: 'acme', teamId: 'team-1' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('team-dashboard-recent-ready')).toBeInTheDocument();
    });
    expect(screen.getByTestId('team-dashboard-recent-ready')).toHaveTextContent('12');
  });

  it('renders blocked_count card', async () => {
    render(<TeamDashboardPage params={{ slug: 'acme', teamId: 'team-1' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('team-dashboard-blocked')).toBeInTheDocument();
    });
    expect(screen.getByTestId('team-dashboard-blocked')).toHaveTextContent('1');
  });

  it('renders pending_reviews card', async () => {
    render(<TeamDashboardPage params={{ slug: 'acme', teamId: 'team-1' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('team-dashboard-pending-reviews')).toBeInTheDocument();
    });
    expect(screen.getByTestId('team-dashboard-pending-reviews')).toHaveTextContent('3');
  });

  it('renders owned_by_state distribution', async () => {
    render(<TeamDashboardPage params={{ slug: 'acme', teamId: 'team-1' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('team-dashboard-state-distribution')).toBeInTheDocument();
    });
  });

  it('shows error state on 5xx', async () => {
    setupTeamHandler(mockTeamData, 500);
    render(<TeamDashboardPage params={{ slug: 'acme', teamId: 'team-1' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('team-dashboard-error')).toBeInTheDocument();
    });
  });
});
