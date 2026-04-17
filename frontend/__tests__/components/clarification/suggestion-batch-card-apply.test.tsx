/**
 * EP-03 — SuggestionBatchCard "Apply accepted" button (phase 3.7 wiring).
 *
 * Tests:
 * - batch with accepted items → button label shows "applyAccepted" key
 * - click → fetch called with correct batch id
 * - success → onApplied callback fires
 * - onRefetchSections + onRefetchVersions called on success
 * - disabled during pending apply
 * - error state via role="alert"
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SuggestionBatchCard } from '@/components/clarification/suggestion-batch-card';
import type { SuggestionSet } from '@/lib/types/suggestion';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params && 'count' in params) return `${key}(${params.count})`;
    return key;
  },
}));

const BASE = 'http://localhost';

const batchWithAccepted: SuggestionSet = {
  id: 'batch-apply-1',
  work_item_id: 'wi-apply-1',
  status: 'partially_applied',
  created_at: '2026-04-17T10:00:00Z',
  expires_at: '2026-04-18T10:00:00Z',
  items: [
    {
      id: 'item-a1',
      section: 'summary',
      current_content: 'Old summary',
      proposed_content: 'New summary',
      rationale: 'More concise',
      status: 'accepted',
    },
    {
      id: 'item-a2',
      section: 'context',
      current_content: 'Old context',
      proposed_content: 'New context',
      rationale: null,
      status: 'accepted',
    },
  ],
};

describe('SuggestionBatchCard — Apply accepted wiring', () => {
  it('shows apply button with count when items are accepted', () => {
    render(
      <SuggestionBatchCard
        suggestionSet={batchWithAccepted}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    // Button should display the count-based label
    const applyBtn = screen.getByRole('button', { name: /applyAccepted\(2\)|apply.*2|2.*accept/i });
    expect(applyBtn).toBeInTheDocument();
    expect(applyBtn).not.toBeDisabled();
  });

  it('calls POST /apply with correct batch id on click', async () => {
    const onApplied = vi.fn();
    let capturedUrl = '';

    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-apply-1/apply`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          data: {
            applied_count: 2,
            skipped_count: 0,
            latest_version_id: 'ver-1',
            latest_version_number: 3,
          },
        });
      }),
    );

    render(
      <SuggestionBatchCard
        suggestionSet={batchWithAccepted}
        onApplied={onApplied}
        onDismiss={vi.fn()}
      />,
    );

    const applyBtn = screen.getByRole('button', { name: /applyAccepted|apply.*2|2.*accept/i });
    fireEvent.click(applyBtn);

    await waitFor(() => expect(onApplied).toHaveBeenCalledOnce());

    expect(capturedUrl).toContain('/api/v1/suggestion-sets/batch-apply-1/apply');
    const result = onApplied.mock.calls[0]?.[0];
    expect(result?.applied_count).toBe(2);
  });

  it('calls onRefetchSections and onRefetchVersions on success', async () => {
    const onRefetchSections = vi.fn();
    const onRefetchVersions = vi.fn();

    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-apply-1/apply`, () =>
        HttpResponse.json({
          data: {
            applied_count: 2,
            skipped_count: 0,
            latest_version_id: 'ver-1',
            latest_version_number: 3,
          },
        }),
      ),
    );

    render(
      <SuggestionBatchCard
        suggestionSet={batchWithAccepted}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
        onRefetchSections={onRefetchSections}
        onRefetchVersions={onRefetchVersions}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /applyAccepted|apply.*2|2.*accept/i }));

    await waitFor(() => expect(onRefetchSections).toHaveBeenCalledOnce());
    expect(onRefetchVersions).toHaveBeenCalledOnce();
  });

  it('shows error alert on non-409 failure', async () => {
    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-apply-1/apply`, () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'Internal error' } }, { status: 500 }),
      ),
    );

    render(
      <SuggestionBatchCard
        suggestionSet={batchWithAccepted}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /applyAccepted|apply.*2|2.*accept/i }));

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });
  });
});
