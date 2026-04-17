import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ValidationsChecklist } from '@/components/work-item/validations-checklist';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return `${ns}.${key}(${JSON.stringify(params)})`;
    }
    return `${ns}.${key}`;
  },
}));

const BASE = 'http://localhost';

const CHECKLIST = {
  data: {
    required: [
      { rule_id: 'r1', label: 'Has acceptance criteria', required: true, status: 'pending', passed_at: null, passed_by_review_request_id: null, waived_at: null, waived_by: null },
      { rule_id: 'r2', label: 'Has description', required: true, status: 'passed', passed_at: '2026-01-10T00:00:00Z', passed_by_review_request_id: null, waived_at: null, waived_by: null },
    ],
    recommended: [
      { rule_id: 'rec1', label: 'Has examples', required: false, status: 'pending', passed_at: null, passed_by_review_request_id: null, waived_at: null, waived_by: null },
      { rule_id: 'rec2', label: 'Has priority', required: false, status: 'waived', passed_at: null, passed_by_review_request_id: null, waived_at: '2026-01-11T00:00:00Z', waived_by: 'alice' },
    ],
  },
};

function setupHandlers() {
  server.use(
    http.get(`${BASE}/api/v1/work-items/wi-1/validations`, () =>
      HttpResponse.json(CHECKLIST),
    ),
  );
}

describe('ValidationsChecklist', () => {
  it('renders required and recommended sections after loading', async () => {
    setupHandlers();
    render(<ValidationsChecklist workItemId="wi-1" isOwner={false} />);
    await waitFor(() =>
      expect(screen.getByText('workspace.itemDetail.validations.requiredSection')).toBeInTheDocument(),
    );
    expect(screen.getByText('workspace.itemDetail.validations.recommendedSection')).toBeInTheDocument();
  });

  it('shows passed rule with green indicator and pending with gray', async () => {
    setupHandlers();
    render(<ValidationsChecklist workItemId="wi-1" isOwner={false} />);
    await waitFor(() => screen.getByText('Has description'));
    expect(screen.getByTestId('rule-status-r2')).toHaveAttribute('data-status', 'passed');
    expect(screen.getByTestId('rule-status-r1')).toHaveAttribute('data-status', 'pending');
  });

  it('shows waived badge for waived rule', async () => {
    setupHandlers();
    render(<ValidationsChecklist workItemId="wi-1" isOwner={false} />);
    await waitFor(() => screen.getByText('Has priority'));
    expect(screen.getByTestId('rule-status-rec2')).toHaveAttribute('data-status', 'waived');
  });

  it('renders footer progress: mandatory satisfied/total and gate chip', async () => {
    setupHandlers();
    render(<ValidationsChecklist workItemId="wi-1" isOwner={false} />);
    await waitFor(() =>
      expect(screen.getByTestId('validations-footer')).toBeInTheDocument(),
    );
    // 1 of 2 required passed
    expect(screen.getByTestId('validations-footer')).toHaveTextContent('1');
    expect(screen.getByTestId('gate-chip')).toBeInTheDocument();
  });

  it('shows Waive button for pending recommended rule when isOwner=true, not for required', async () => {
    setupHandlers();
    render(<ValidationsChecklist workItemId="wi-1" isOwner={true} />);
    await waitFor(() => screen.getByText('Has examples'));
    // recommended pending → waive button
    const waiveButtons = screen.getAllByRole('button', {
      name: /workspace\.itemDetail\.validations\.waiveButton/i,
    });
    expect(waiveButtons.length).toBeGreaterThan(0);
    // required rule r1 (pending) → no waive button in that row
    expect(screen.queryByTestId('waive-btn-r1')).not.toBeInTheDocument();
  });

  it('waive button calls waive API and re-renders', async () => {
    const user = userEvent.setup();
    setupHandlers();
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/validations/rec1/waive`, () =>
        HttpResponse.json({ data: { rule_id: 'rec1', status: 'waived', waived_at: '2026-04-17T00:00:00Z', waived_by: 'me' } }),
      ),
    );
    render(<ValidationsChecklist workItemId="wi-1" isOwner={true} />);
    await waitFor(() => screen.getByText('Has examples'));

    const waiveBtn = screen.getByTestId('waive-btn-rec1');
    await user.click(waiveBtn);
    // confirm dialog appears
    await waitFor(() =>
      screen.getByText('workspace.itemDetail.validations.waiveConfirmTitle'),
    );
    const confirmBtn = screen.getByRole('button', {
      name: /workspace\.itemDetail\.validations\.waiveConfirmButton/i,
    });
    await user.click(confirmBtn);
    // After waive, re-fetches — optimistic update sets waived
    await waitFor(() =>
      expect(screen.getByTestId('rule-status-rec1')).toHaveAttribute('data-status', 'waived'),
    );
  });
});
