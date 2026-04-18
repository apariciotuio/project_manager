/**
 * EP-09 — PersonDashboard tests.
 * RED phase: tests written before implementation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import PersonDashboardPage from '@/app/workspace/[slug]/dashboard/me/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/workspace/acme/dashboard/me',
  useParams: () => ({ slug: 'acme' }),
  useSearchParams: () => ({ get: () => null, toString: () => '' }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockUser = {
  id: 'user-1',
  email: 'a@b.com',
  full_name: 'Test User',
  avatar_url: null,
  workspace_id: 'ws-1',
  workspace_slug: 'acme',
  is_superadmin: false,
};

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
  }),
}));

const mockPersonData = {
  owned_by_state: { draft: 3, in_clarification: 2, in_review: 1 },
  overloaded: false,
  pending_reviews_count: 4,
  inbox_count: 7,
};

function setupPersonHandler(data = mockPersonData, status = 200) {
  server.use(
    http.get('http://localhost/api/v1/dashboards/person/:userId', () =>
      status === 200
        ? HttpResponse.json({ data, message: 'ok' })
        : HttpResponse.json({ error: { message: 'Forbidden', code: 'FORBIDDEN', details: {} } }, { status }),
    ),
  );
}

describe('PersonDashboardPage', () => {
  beforeEach(() => {
    setupPersonHandler();
  });

  it('renders loading state initially', () => {
    render(<PersonDashboardPage params={{ slug: 'acme' }} />);
    expect(screen.getByTestId('person-dashboard-skeleton')).toBeInTheDocument();
  });

  it('renders inbox count card', async () => {
    render(<PersonDashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('person-dashboard-inbox')).toBeInTheDocument();
    });
    expect(screen.getByTestId('person-dashboard-inbox')).toHaveTextContent('7');
  });

  it('renders pending reviews count card', async () => {
    render(<PersonDashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('person-dashboard-pending-reviews')).toBeInTheDocument();
    });
    expect(screen.getByTestId('person-dashboard-pending-reviews')).toHaveTextContent('4');
  });

  it('renders owned_by_state distribution', async () => {
    render(<PersonDashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('person-dashboard-state-distribution')).toBeInTheDocument();
    });
  });

  it('shows no-permission empty state on 403', async () => {
    setupPersonHandler(mockPersonData, 403);
    render(<PersonDashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('person-dashboard-no-permission')).toBeInTheDocument();
    });
  });

  it('shows error state on 5xx', async () => {
    server.use(
      http.get('http://localhost/api/v1/dashboards/person/:userId', () =>
        HttpResponse.json({ error: { message: 'Server error', code: 'INTERNAL', details: {} } }, { status: 500 }),
      ),
    );
    render(<PersonDashboardPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('person-dashboard-error')).toBeInTheDocument();
    });
  });
});
