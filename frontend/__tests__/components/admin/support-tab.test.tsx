/**
 * EP-10: Support Tools Tab — RED tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

function setupDefaultHandlers() {
  server.use(
    http.get('http://localhost/api/v1/admin/support/orphaned-work-items', () =>
      HttpResponse.json({
        data: [{
          id: 'wi1', title: 'Orphaned Task', owner_id: 'u99',
          owner_display: 'Gone User', owner_state: 'deleted', created_at: '2026-01-01T00:00:00Z',
        }],
        message: 'ok',
      })
    ),
    http.get('http://localhost/api/v1/admin/support/pending-invitations', () =>
      HttpResponse.json({
        data: [{
          id: 'inv1', email: 'new@test.com',
          expires_at: '2026-05-01T00:00:00Z', expiring_soon: false,
        }],
        message: 'ok',
      })
    ),
    http.get('http://localhost/api/v1/admin/support/failed-exports', () =>
      HttpResponse.json({
        data: [{
          id: 'fe1', work_item_id: 'wi2', work_item_title: 'Failed Export',
          error_code: 'JIRA_UNREACHABLE', attempt_count: 3, created_at: '2026-01-01T00:00:00Z',
        }],
        message: 'ok',
      })
    ),
    http.get('http://localhost/api/v1/admin/support/config-blocked-work-items', () =>
      HttpResponse.json({
        data: [{
          id: 'wi3', title: 'Blocked Item', blocking_reason: 'suspended_owner',
        }],
        message: 'ok',
      })
    )
  );
}

async function renderSupportTab() {
  const { SupportTab } = await import('@/components/admin/support-tab');
  return render(<SupportTab />);
}

describe('SupportTab', () => {
  beforeEach(setupDefaultHandlers);

  it('renders orphaned work items section with count badge', async () => {
    await renderSupportTab();
    await waitFor(() => {
      expect(screen.getByText('Orphaned Task')).toBeInTheDocument();
    });
  });

  it('renders pending invitations section', async () => {
    await renderSupportTab();
    await waitFor(() => {
      expect(screen.getByText('new@test.com')).toBeInTheDocument();
    });
  });

  it('renders failed exports section', async () => {
    await renderSupportTab();
    await waitFor(() => {
      expect(screen.getByText('Failed Export')).toBeInTheDocument();
    });
  });

  it('renders config-blocked items grouped by blocking reason', async () => {
    await renderSupportTab();
    await waitFor(() => {
      expect(screen.getByText('Blocked Item')).toBeInTheDocument();
    });
  });

  it('retry-all button calls retry endpoint', async () => {
    let retried = false;
    server.use(
      http.post('http://localhost/api/v1/admin/support/failed-exports/retry-all', () => {
        retried = true;
        return HttpResponse.json({ data: { queued: 1 }, message: 'ok' }, { status: 202 });
      })
    );
    await renderSupportTab();
    await waitFor(() => screen.getByText('Failed Export'));
    const retryBtn = screen.getByRole('button', { name: /retry all/i });
    await userEvent.click(retryBtn);
    await waitFor(() => expect(retried).toBe(true));
  });
});
