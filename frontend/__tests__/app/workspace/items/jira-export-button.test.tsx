/**
 * EP-11 — JiraExportButton tests
 *
 * Tests:
 * 1. Button hidden when canExport=false
 * 2. Button renders when canExport=true
 * 3. On click → POST /api/v1/work-items/{id}/export/jira → 202 → "Export queued" toast + button disabled
 * 4. On 401/403 → showErrorToast called
 * 5. On 5xx → showErrorToast called with retry message
 * 6. Jira key link renders when external_jira_key set
 * 7. Jira key link absent when external_jira_key is null
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../../msw/server';
import { JiraExportButton } from '@/components/work-item/jira-export-button';
import * as toastModule from '@/lib/errors/toast';

const BASE = 'http://localhost';
const ITEM_ID = 'wi-99';
const EXPORT_URL = `${BASE}/api/v1/work-items/${ITEM_ID}/export/jira`;

vi.mock('@/lib/errors/toast', async (importOriginal) => {
  const real = await importOriginal<typeof toastModule>();
  return {
    ...real,
    showErrorToast: vi.fn(),
  };
});

const showErrorToastMock = vi.mocked(toastModule.showErrorToast);

function renderButton({
  canExport = true,
  externalJiraKey = null,
}: {
  canExport?: boolean;
  externalJiraKey?: string | null;
} = {}) {
  return render(
    <JiraExportButton
      workItemId={ITEM_ID}
      canExport={canExport}
      externalJiraKey={externalJiraKey}
      jiraBaseUrl="https://jira.example.com"
    />,
  );
}

describe('JiraExportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── Visibility ──────────────────────────────────────────────────────────────

  it('renders nothing when canExport is false', () => {
    renderButton({ canExport: false });
    expect(screen.queryByTestId('jira-export-button')).toBeNull();
    expect(screen.queryByTestId('jira-export-wrapper')).toBeNull();
  });

  it('renders the button when canExport is true', () => {
    renderButton({ canExport: true });
    expect(screen.getByTestId('jira-export-button')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export to jira/i })).toBeInTheDocument();
  });

  // ── 202 success flow ────────────────────────────────────────────────────────

  it('shows "Export queued" status and disables button after 202', async () => {
    server.use(
      http.post(EXPORT_URL, () =>
        HttpResponse.json({ data: { job_id: 'j-1', status: 'queued' } }, { status: 202 }),
      ),
    );

    renderButton();
    await userEvent.click(screen.getByTestId('jira-export-button'));

    await waitFor(() =>
      expect(screen.getByTestId('jira-export-success')).toHaveTextContent('Export queued'),
    );

    expect(screen.getByTestId('jira-export-button')).toBeDisabled();
  });

  it('re-enables the button after 30 s lockout', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    server.use(
      http.post(EXPORT_URL, () =>
        HttpResponse.json({ data: { job_id: 'j-1', status: 'queued' } }, { status: 202 }),
      ),
    );

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) });
    renderButton();
    await user.click(screen.getByTestId('jira-export-button'));

    await waitFor(() =>
      expect(screen.getByTestId('jira-export-button')).toBeDisabled(),
    );

    vi.advanceTimersByTime(30_001);

    await waitFor(() =>
      expect(screen.getByTestId('jira-export-button')).not.toBeDisabled(),
    );
  });

  // ── Error flows ─────────────────────────────────────────────────────────────

  it('calls showErrorToast on 401 (session expired)', async () => {
    // api-client retries 401 via /auth/refresh; refresh also 401 → UnauthenticatedError
    server.use(
      http.post(EXPORT_URL, () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'Not authenticated' } },
          { status: 401 },
        ),
      ),
      http.post(`${BASE}/api/v1/auth/refresh`, () =>
        HttpResponse.json({ error: { code: 'UNAUTHORIZED', message: 'Token expired' } }, { status: 401 }),
      ),
    );

    renderButton();
    await userEvent.click(screen.getByTestId('jira-export-button'));

    await waitFor(() => expect(showErrorToastMock).toHaveBeenCalledOnce());
    const [code] = showErrorToastMock.mock.calls[0]!;
    expect(code).toBe('EXPORT_FORBIDDEN');
  });

  it('calls showErrorToast on 403', async () => {
    server.use(
      http.post(EXPORT_URL, () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'Not authorised' } },
          { status: 403 },
        ),
      ),
    );

    renderButton();
    await userEvent.click(screen.getByTestId('jira-export-button'));

    await waitFor(() => expect(showErrorToastMock).toHaveBeenCalledOnce());
    const [code] = showErrorToastMock.mock.calls[0]!;
    expect(code).toBe('EXPORT_FORBIDDEN');
  });

  it('calls showErrorToast with retry message on 500', async () => {
    server.use(
      http.post(EXPORT_URL, () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL_ERROR', message: 'Server error' } },
          { status: 500 },
        ),
      ),
    );

    renderButton();
    await userEvent.click(screen.getByTestId('jira-export-button'));

    await waitFor(() => expect(showErrorToastMock).toHaveBeenCalledOnce());
    const [, message] = showErrorToastMock.mock.calls[0]!;
    expect(message).toMatch(/retry/i);
  });

  // ── Jira key link ───────────────────────────────────────────────────────────

  it('renders a Jira link when external_jira_key is set', () => {
    renderButton({ externalJiraKey: 'PROJ-42' });
    const link = screen.getByTestId('jira-issue-link');
    expect(link).toBeInTheDocument();
    expect(link).toHaveTextContent('Jira: PROJ-42');
    expect(link).toHaveAttribute('href', 'https://jira.example.com/browse/PROJ-42');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('does not render Jira link when external_jira_key is null', () => {
    renderButton({ externalJiraKey: null });
    expect(screen.queryByTestId('jira-issue-link')).toBeNull();
  });
});
