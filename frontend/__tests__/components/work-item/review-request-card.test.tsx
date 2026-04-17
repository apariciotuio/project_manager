import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewRequestCard } from '@/components/work-item/review-request-card';
import type { ReviewRequestWithResponses } from '@/lib/api/reviews';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${ns}.${key}(${JSON.stringify(params)})`;
    return `${ns}.${key}`;
  },
}));

const PENDING_REQUEST: ReviewRequestWithResponses = {
  id: 'req-1',
  work_item_id: 'wi-1',
  version_id: 'v-1',
  reviewer_type: 'user',
  reviewer_id: 'user-2',
  team_id: null,
  validation_rule_id: null,
  status: 'pending',
  requested_by: 'user-1',
  requested_at: '2026-04-01T00:00:00Z',
  cancelled_at: null,
  version_outdated: false,
  requested_version: 1,
  current_version: 1,
  responses: [],
};

const OUTDATED_REQUEST: ReviewRequestWithResponses = {
  ...PENDING_REQUEST,
  id: 'req-2',
  version_outdated: true,
  requested_version: 1,
  current_version: 3,
};

const CLOSED_REQUEST: ReviewRequestWithResponses = {
  ...PENDING_REQUEST,
  id: 'req-3',
  status: 'closed',
  responses: [
    {
      id: 'resp-1',
      review_request_id: 'req-3',
      responder_id: 'user-2',
      decision: 'approved',
      content: 'Looks good',
      responded_at: '2026-04-02T00:00:00Z',
    },
  ],
};

describe('ReviewRequestCard', () => {
  it('renders reviewer id and pending status badge', () => {
    render(
      <ReviewRequestCard
        request={PENDING_REQUEST}
        currentUserId="user-1"
        onCancel={vi.fn()}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByTestId('review-status-badge')).toHaveAttribute('data-status', 'pending');
  });

  it('shows yellow outdated banner when version_outdated=true', () => {
    render(
      <ReviewRequestCard
        request={OUTDATED_REQUEST}
        currentUserId="user-1"
        onCancel={vi.fn()}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByTestId('outdated-banner')).toBeInTheDocument();
  });

  it('shows Cancel button when pending and current user is requester', () => {
    const onCancel = vi.fn();
    render(
      <ReviewRequestCard
        request={PENDING_REQUEST}
        currentUserId="user-1"
        onCancel={onCancel}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByTestId('cancel-btn')).toBeInTheDocument();
  });

  it('does not show Cancel button when current user is not requester', () => {
    render(
      <ReviewRequestCard
        request={PENDING_REQUEST}
        currentUserId="user-99"
        onCancel={vi.fn()}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('cancel-btn')).not.toBeInTheDocument();
  });

  it('clicking Cancel calls onCancel with request id', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <ReviewRequestCard
        request={PENDING_REQUEST}
        currentUserId="user-1"
        onCancel={onCancel}
        onRespond={vi.fn()}
      />,
    );
    await user.click(screen.getByTestId('cancel-btn'));
    expect(onCancel).toHaveBeenCalledWith('req-1');
  });

  it('shows response decision chip for closed request with approved decision', () => {
    render(
      <ReviewRequestCard
        request={CLOSED_REQUEST}
        currentUserId="user-1"
        onCancel={vi.fn()}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByTestId('decision-chip')).toHaveAttribute('data-decision', 'approved');
  });

  it('shows Respond button for reviewer when pending', () => {
    render(
      <ReviewRequestCard
        request={PENDING_REQUEST}
        currentUserId="user-2"
        onCancel={vi.fn()}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByTestId('respond-btn')).toBeInTheDocument();
  });
});
