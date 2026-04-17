import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { RequestReviewDialog } from '@/components/work-item/request-review-dialog';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${ns}.${key}(${JSON.stringify(params)})`;
    return `${ns}.${key}`;
  },
}));

const BASE = 'http://localhost';

const MEMBERS = {
  data: [
    { id: 'user-2', email: 'bob@example.com', full_name: 'Bob Smith', avatar_url: null, role: 'member' },
    { id: 'user-3', email: 'carol@example.com', full_name: 'Carol Jones', avatar_url: null, role: 'member' },
  ],
};

function setupMembers() {
  server.use(
    http.get(`${BASE}/api/v1/workspaces/members`, () => HttpResponse.json(MEMBERS)),
  );
}

describe('RequestReviewDialog', () => {
  it('renders dialog with reviewer select when open', async () => {
    setupMembers();
    render(
      <RequestReviewDialog
        workItemId="wi-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('reviewer-select')).toBeInTheDocument();
  });

  it('does not render when open=false', () => {
    render(
      <RequestReviewDialog
        workItemId="wi-1"
        open={false}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('submits POST and calls onSuccess', async () => {
    const user = userEvent.setup();
    setupMembers();
    const onSuccess = vi.fn();
    const CREATED = {
      data: {
        id: 'req-new',
        work_item_id: 'wi-1',
        version_id: 'v-1',
        reviewer_type: 'user',
        reviewer_id: 'user-2',
        team_id: null,
        validation_rule_id: null,
        status: 'pending',
        requested_by: 'me',
        requested_at: '2026-04-17T00:00:00Z',
        cancelled_at: null,
      },
    };
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/review-requests`, () =>
        HttpResponse.json(CREATED, { status: 201 }),
      ),
    );
    render(
      <RequestReviewDialog
        workItemId="wi-1"
        versionId="v-1"
        open={true}
        onSuccess={onSuccess}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByTestId('reviewer-select'));

    // Select reviewer
    await user.click(screen.getByTestId('reviewer-select'));
    await waitFor(() => screen.getByText('Bob Smith'));
    await user.click(screen.getByText('Bob Smith'));

    // Submit
    await user.click(screen.getByTestId('submit-btn'));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it('shows forbidden error inline when server returns 403', async () => {
    const user = userEvent.setup();
    setupMembers();
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/review-requests`, () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'forbidden' } }, { status: 403 }),
      ),
    );
    render(
      <RequestReviewDialog
        workItemId="wi-1"
        versionId="v-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByTestId('reviewer-select'));

    await user.click(screen.getByTestId('reviewer-select'));
    await waitFor(() => screen.getByText('Bob Smith'));
    await user.click(screen.getByText('Bob Smith'));
    await user.click(screen.getByTestId('submit-btn'));

    await waitFor(() =>
      expect(screen.getByTestId('inline-error')).toBeInTheDocument(),
    );
  });

  it('calls onClose when cancel is clicked', async () => {
    const user = userEvent.setup();
    setupMembers();
    const onClose = vi.fn();
    render(
      <RequestReviewDialog
        workItemId="wi-1"
        open={true}
        onSuccess={vi.fn()}
        onClose={onClose}
      />,
    );
    await waitFor(() => screen.getByRole('dialog'));
    await user.click(screen.getByTestId('cancel-btn'));
    expect(onClose).toHaveBeenCalled();
  });
});
