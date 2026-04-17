import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ReviewsTab } from '@/components/work-item/reviews-tab';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${ns}.${key}(${JSON.stringify(params)})`;
    return `${ns}.${key}`;
  },
}));

const BASE = 'http://localhost';

const CHECKLIST = {
  data: {
    required: [
      {
        rule_id: 'r1', label: 'Has AC', required: true,
        status: 'passed', passed_at: '2026-01-01T00:00:00Z',
        passed_by_review_request_id: null, waived_at: null, waived_by: null,
      },
    ],
    recommended: [],
  },
};

const REVIEW_REQUESTS = {
  data: [
    {
      id: 'req-1', work_item_id: 'wi-1', version_id: 'v-1',
      reviewer_type: 'user', reviewer_id: 'user-2', team_id: null,
      validation_rule_id: null, status: 'pending', requested_by: 'user-1',
      requested_at: '2026-04-01T00:00:00Z', cancelled_at: null,
      version_outdated: false, requested_version: 1, current_version: 1,
      responses: [],
    },
  ],
};

const MEMBERS = { data: [] };

function setupHandlers() {
  server.use(
    http.get(`${BASE}/api/v1/work-items/wi-1/validations`, () => HttpResponse.json(CHECKLIST)),
    http.get(`${BASE}/api/v1/work-items/wi-1/review-requests`, () => HttpResponse.json(REVIEW_REQUESTS)),
    http.get(`${BASE}/api/v1/workspaces/members`, () => HttpResponse.json(MEMBERS)),
  );
}

describe('ReviewsTab', () => {
  it('renders ValidationsChecklist section', async () => {
    setupHandlers();
    render(<ReviewsTab workItemId="wi-1" currentUserId="user-1" isOwner={false} />);
    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.validations.requiredSection')).toBeInTheDocument(),
    );
  });

  it('renders review request cards after loading', async () => {
    setupHandlers();
    render(<ReviewsTab workItemId="wi-1" currentUserId="user-1" isOwner={false} />);
    await waitFor(() =>
      expect(screen.getByTestId('review-status-badge')).toBeInTheDocument(),
    );
  });

  it('shows empty state when no review requests', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/validations`, () => HttpResponse.json(CHECKLIST)),
      http.get(`${BASE}/api/v1/work-items/wi-1/review-requests`, () => HttpResponse.json({ data: [] })),
      http.get(`${BASE}/api/v1/workspaces/members`, () => HttpResponse.json(MEMBERS)),
    );
    render(<ReviewsTab workItemId="wi-1" currentUserId="user-1" isOwner={false} />);
    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.reviews.empty')).toBeInTheDocument(),
    );
  });

  it('shows "Request review" button for owner and opens dialog on click', async () => {
    const user = userEvent.setup();
    setupHandlers();
    render(<ReviewsTab workItemId="wi-1" currentUserId="user-1" isOwner={true} />);
    await waitFor(() =>
      expect(screen.getByTestId('request-review-btn')).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId('request-review-btn'));
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    );
  });

  it('does not show "Request review" button for non-owner', async () => {
    setupHandlers();
    render(<ReviewsTab workItemId="wi-1" currentUserId="user-99" isOwner={false} />);
    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.validations.requiredSection')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('request-review-btn')).not.toBeInTheDocument();
  });
});
