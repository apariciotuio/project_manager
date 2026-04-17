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
  ],
};

function setupMembers() {
  server.use(
    http.get(`${BASE}/api/v1/workspaces/members`, () => HttpResponse.json(MEMBERS)),
  );
}

describe('RequestReviewDialog — versionId prop', () => {
  it('disables submit button and shows hint when versionId is null', async () => {
    setupMembers();
    render(
      <RequestReviewDialog
        workItemId="wi-1"
        versionId={null}
        open={true}
        onSuccess={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => screen.getByTestId('reviewer-select'));

    const submitBtn = screen.getByTestId('submit-btn');
    expect(submitBtn).toBeDisabled();

    // Hint text visible
    expect(screen.getByTestId('version-pending-hint')).toBeTruthy();
  });

  it('includes real versionId in POST body when provided', async () => {
    const user = userEvent.setup();
    setupMembers();

    let requestBody: Record<string, unknown> = {};
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/review-requests`, async ({ request }) => {
        requestBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            data: {
              id: 'req-new',
              work_item_id: 'wi-1',
              version_id: 'ver-abc',
              reviewer_type: 'user',
              reviewer_id: 'user-2',
              team_id: null,
              validation_rule_id: null,
              status: 'pending',
              requested_by: 'me',
              requested_at: '2026-04-17T00:00:00Z',
              cancelled_at: null,
            },
          },
          { status: 201 },
        );
      }),
    );

    render(
      <RequestReviewDialog
        workItemId="wi-1"
        versionId="ver-abc"
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

    await waitFor(() => {
      expect(requestBody['version_id']).toBe('ver-abc');
    });
  });
});
