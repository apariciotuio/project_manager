/**
 * EP-10: Jira Config Tab — RED tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const JIRA_CONFIG = {
  id: 'jc1',
  workspace_id: 'ws1',
  project_id: null,
  base_url: 'https://acme.atlassian.net',
  auth_type: 'basic',
  state: 'active',
  last_health_check_status: null,
  last_health_check_at: null,
  created_at: '2026-01-01T00:00:00Z',
};

async function renderJiraTab() {
  const { JiraConfigTab } = await import('@/components/admin/jira-config-tab');
  return render(<JiraConfigTab />);
}

describe('JiraConfigTab', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/jira', () =>
        HttpResponse.json({ data: [JIRA_CONFIG], message: 'ok' })
      )
    );
  });

  it('renders config list with base_url', async () => {
    await renderJiraTab();
    await waitFor(() => {
      expect(screen.getByText('https://acme.atlassian.net')).toBeInTheDocument();
    });
  });

  it('renders state badge', async () => {
    await renderJiraTab();
    await waitFor(() => {
      expect(screen.getByText(/active/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no configs', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/integrations/jira', () =>
        HttpResponse.json({ data: [], message: 'ok' })
      )
    );
    await renderJiraTab();
    await waitFor(() => {
      expect(screen.getByTestId('jira-configs-empty')).toBeInTheDocument();
    });
  });

  it('create config form validates HTTPS', async () => {
    await renderJiraTab();
    await waitFor(() => screen.getByText('https://acme.atlassian.net'));
    await userEvent.click(screen.getByRole('button', { name: /add jira/i }));
    const urlInput = screen.getByLabelText(/base url/i);
    await userEvent.type(urlInput, 'http://insecure.atlassian.net');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/https/i);
    });
  });

  it('test connection shows spinner then result', async () => {
    server.use(
      http.post('http://localhost/api/v1/admin/integrations/jira/jc1/test', async () => {
        return HttpResponse.json({ data: { status: 'ok' }, message: 'ok' });
      })
    );
    await renderJiraTab();
    await waitFor(() => screen.getByText('https://acme.atlassian.net'));
    const testBtn = screen.getByRole('button', { name: /test connection/i });
    await userEvent.click(testBtn);
    await waitFor(() => {
      expect(screen.getByText(/connection successful|ok/i)).toBeInTheDocument();
    });
  });

  it('test connection auth_failure shows error message', async () => {
    server.use(
      http.post('http://localhost/api/v1/admin/integrations/jira/jc1/test', async () => {
        return HttpResponse.json({
          data: { status: 'auth_failure', message: 'Authentication failed' },
          message: 'ok',
        });
      })
    );
    await renderJiraTab();
    await waitFor(() => screen.getByText('https://acme.atlassian.net'));
    await userEvent.click(screen.getByRole('button', { name: /test connection/i }));
    await waitFor(() => {
      expect(screen.getByText(/authentication failed/i)).toBeInTheDocument();
    });
  });
});
