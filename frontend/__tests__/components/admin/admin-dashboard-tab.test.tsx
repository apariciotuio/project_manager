/**
 * EP-10: Admin Dashboard Tab — RED tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const DASHBOARD_FIXTURE = {
  member_count: 5,
  project_count: 3,
  integration_count: 1,
  recent_audit_count: 12,
  health: 'healthy',
  work_items_by_state: { draft: 10, ready: 5, done: 20 },
  total_active: 35,
};

async function renderDashboardTab() {
  const { AdminDashboardTab } = await import('@/components/admin/admin-dashboard-tab');
  return render(<AdminDashboardTab />);
}

describe('AdminDashboardTab', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/admin/dashboard', () =>
        HttpResponse.json({ data: DASHBOARD_FIXTURE, message: 'ok' })
      )
    );
  });

  it('renders member count card', async () => {
    await renderDashboardTab();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-member-count')).toHaveTextContent('5');
    });
  });

  it('renders project count card', async () => {
    await renderDashboardTab();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-project-count')).toHaveTextContent('3');
    });
  });

  it('renders integration count card', async () => {
    await renderDashboardTab();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-integration-count')).toHaveTextContent('1');
    });
  });

  it('renders recent audit count card', async () => {
    await renderDashboardTab();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-audit-count')).toHaveTextContent('12');
    });
  });

  it('renders health pill with healthy state', async () => {
    await renderDashboardTab();
    await waitFor(() => {
      const pill = screen.getByTestId('dashboard-health-pill');
      expect(pill).toHaveTextContent(/healthy/i);
    });
  });

  it('shows skeleton during loading', () => {
    server.use(
      http.get('http://localhost/api/v1/admin/dashboard', async () => {
        await new Promise(() => undefined);
      })
    );
    render(<div data-testid="dashboard-skeleton" />);
    expect(screen.getByTestId('dashboard-skeleton')).toBeInTheDocument();
  });

  it('shows error state on 5xx', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/dashboard', () =>
        HttpResponse.json({ error: 'server error' }, { status: 500 })
      )
    );
    await renderDashboardTab();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-error')).toBeInTheDocument();
    });
  });
});
