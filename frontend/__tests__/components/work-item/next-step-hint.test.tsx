import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { NextStepHint } from '@/components/work-item/next-step-hint';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const BASE = 'http://localhost';

describe('NextStepHint', () => {
  it('renders skeleton while loading', () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );
    render(<NextStepHint workItemId="wi-1" />);
    // While loading, no message visible
    expect(screen.queryByText(/step/i)).not.toBeInTheDocument();
  });

  it('renders hint message', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, () =>
        HttpResponse.json({
          data: {
            next_step: 'fill_blocking_gaps',
            message: 'Fill blocking gaps to proceed.',
            blocking: true,
            gaps_referenced: ['acceptance_criteria'],
            suggested_validators: [],
          },
        })
      )
    );

    render(<NextStepHint workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByText('Fill blocking gaps to proceed.')).toBeInTheDocument()
    );
  });

  it('shows terminal state message when next_step is null', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, () =>
        HttpResponse.json({
          data: {
            next_step: null,
            message: 'Item has been exported.',
            blocking: false,
            gaps_referenced: [],
            suggested_validators: [],
          },
        })
      )
    );

    render(<NextStepHint workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByTestId('next-step-terminal')).toBeInTheDocument()
    );
  });

  it('shows blocking indicator when blocking=true', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, () =>
        HttpResponse.json({
          data: {
            next_step: 'assign_owner',
            message: 'Assign an owner.',
            blocking: true,
            gaps_referenced: [],
            suggested_validators: [],
          },
        })
      )
    );

    render(<NextStepHint workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByTestId('blocking-badge')).toBeInTheDocument());
  });

  it('does not show blocking indicator when blocking=false', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, () =>
        HttpResponse.json({
          data: {
            next_step: 'request_review',
            message: 'Request a review.',
            blocking: false,
            gaps_referenced: [],
            suggested_validators: [],
          },
        })
      )
    );

    render(<NextStepHint workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('Request a review.')).toBeInTheDocument());
    expect(screen.queryByTestId('blocking-badge')).not.toBeInTheDocument();
  });

  it('renders suggested validators list', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, () =>
        HttpResponse.json({
          data: {
            next_step: 'assign_validators',
            message: 'Assign validators.',
            blocking: false,
            gaps_referenced: [],
            suggested_validators: [
              { role: 'product_owner', reason: 'Required', configured: true },
              { role: 'tech_lead', reason: 'Recommended', configured: false, setup_hint: 'Configure in settings.' },
            ],
          },
        })
      )
    );

    render(<NextStepHint workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('product_owner')).toBeInTheDocument());
    expect(screen.getByText('tech_lead')).toBeInTheDocument();
    // Configured one shows checkmark
    expect(screen.getAllByTestId('validator-configured').length).toBeGreaterThan(0);
    // Unconfigured shows warning
    expect(screen.getAllByTestId('validator-not-configured').length).toBeGreaterThan(0);
  });

  it('shows request_review action when CTA is request_review', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/next-step`, () =>
        HttpResponse.json({
          data: {
            next_step: 'request_review',
            message: 'Request a review to proceed.',
            blocking: false,
            gaps_referenced: [],
            suggested_validators: [],
          },
        })
      )
    );

    render(<NextStepHint workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('Request a review to proceed.')).toBeInTheDocument());
  });
});
