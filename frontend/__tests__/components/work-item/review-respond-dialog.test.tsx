import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ReviewRespondDialog } from '@/components/work-item/review-respond-dialog';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${ns}.${key}(${JSON.stringify(params)})`;
    return `${ns}.${key}`;
  },
}));

const BASE = 'http://localhost';

describe('ReviewRespondDialog', () => {
  it('renders dialog with decision options when open', () => {
    render(
      <ReviewRespondDialog
        reviewRequestId="req-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('decision-approved')).toBeInTheDocument();
    expect(screen.getByTestId('decision-changes_requested')).toBeInTheDocument();
    expect(screen.getByTestId('decision-rejected')).toBeInTheDocument();
  });

  it('hides content textarea when approved is selected', async () => {
    const user = userEvent.setup();
    render(
      <ReviewRespondDialog
        reviewRequestId="req-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await user.click(screen.getByTestId('decision-approved'));
    expect(screen.queryByTestId('content-textarea')).not.toBeInTheDocument();
  });

  it('shows required content textarea when changes_requested selected', async () => {
    const user = userEvent.setup();
    render(
      <ReviewRespondDialog
        reviewRequestId="req-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await user.click(screen.getByTestId('decision-changes_requested'));
    expect(screen.getByTestId('content-textarea')).toBeInTheDocument();
    // submit should be disabled until content is entered
    expect(screen.getByTestId('submit-btn')).toBeDisabled();
  });

  it('submits approved decision without content', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    server.use(
      http.post(`${BASE}/api/v1/review-requests/req-1/response`, () =>
        HttpResponse.json({ data: { id: 'resp-1', review_request_id: 'req-1', responder_id: 'me', decision: 'approved', content: null, responded_at: '2026-04-17T00:00:00Z', responses: [] } }),
      ),
    );
    render(
      <ReviewRespondDialog
        reviewRequestId="req-1"
        open={true}
        onSuccess={onSuccess}
        onClose={vi.fn()}
      />,
    );
    await user.click(screen.getByTestId('decision-approved'));
    await user.click(screen.getByTestId('submit-btn'));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it('shows already-closed error when server returns 409', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${BASE}/api/v1/review-requests/req-1/response`, () =>
        HttpResponse.json(
          { error: { code: 'REVIEW_ALREADY_CLOSED', message: 'already closed' } },
          { status: 409 },
        ),
      ),
    );
    render(
      <ReviewRespondDialog
        reviewRequestId="req-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await user.click(screen.getByTestId('decision-approved'));
    await user.click(screen.getByTestId('submit-btn'));
    await waitFor(() =>
      expect(screen.getByTestId('inline-error')).toBeInTheDocument(),
    );
  });

  it('calls onClose when cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <ReviewRespondDialog
        reviewRequestId="req-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={onClose}
      />,
    );
    await user.click(screen.getByTestId('cancel-btn'));
    expect(onClose).toHaveBeenCalled();
  });
});
