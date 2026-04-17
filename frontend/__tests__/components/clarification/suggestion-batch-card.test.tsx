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

const pendingSet: SuggestionSet = {
  id: 'batch-1',
  work_item_id: 'wi-1',
  status: 'pending',
  created_at: '2026-04-17T10:00:00Z',
  expires_at: '2026-04-18T10:00:00Z',
  items: [
    {
      id: 'item-1',
      section: 'acceptance_criteria',
      current_content: 'Old AC content',
      proposed_content: 'New AC content',
      rationale: 'More specific',
      status: 'pending',
    },
    {
      id: 'item-2',
      section: 'solution_description',
      current_content: 'Old solution',
      proposed_content: 'New solution',
      rationale: null,
      status: 'pending',
    },
    {
      id: 'item-3',
      section: 'scope',
      current_content: 'Old scope',
      proposed_content: 'New scope',
      rationale: 'Clearer',
      status: 'pending',
    },
  ],
};

const expiredSet: SuggestionSet = {
  ...pendingSet,
  status: 'expired',
};

describe('SuggestionBatchCard', () => {
  it('renders one card per item', async () => {
    render(
      <SuggestionBatchCard
        suggestionSet={pendingSet}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    // Expand the card first
    fireEvent.click(screen.getByRole('button', { name: /expand|batch/i }));
    await waitFor(() => expect(screen.getByText('Old AC content')).toBeInTheDocument());
    expect(screen.getByText('New AC content')).toBeInTheDocument();
    expect(screen.getByText('Old solution')).toBeInTheDocument();
  });

  it('Apply Selected is disabled when no items are accepted', () => {
    render(
      <SuggestionBatchCard
        suggestionSet={pendingSet}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /applySelected/i })).toBeDisabled();
  });

  it('Apply button enabled after accepting at least one item', async () => {
    render(
      <SuggestionBatchCard
        suggestionSet={pendingSet}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /expand|batch/i }));
    await waitFor(() => expect(screen.getAllByRole('button', { name: /accept/i })[0]).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: /accept/i })[0]!);
    // After accepting, button shows "applyAccepted(1)" and is enabled
    expect(screen.getByRole('button', { name: /applyAccepted\(1\)/i })).not.toBeDisabled();
  });

  it('Apply button calls onApplied on success', async () => {
    const onApplied = vi.fn();
    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-1/apply`, () =>
        HttpResponse.json({
          data: {
            applied_count: 1,
            skipped_count: 2,
            latest_version_id: 'ver-1',
            latest_version_number: 2,
          },
        }),
      ),
    );

    render(
      <SuggestionBatchCard
        suggestionSet={pendingSet}
        onApplied={onApplied}
        onDismiss={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /expand|batch/i }));
    await waitFor(() => expect(screen.getAllByRole('button', { name: /accept/i })[0]).toBeInTheDocument());

    // Accept item-1
    fireEvent.click(screen.getAllByRole('button', { name: /accept/i })[0]!);

    fireEvent.click(screen.getByRole('button', { name: /applyAccepted\(1\)/i }));
    await waitFor(() => expect(onApplied).toHaveBeenCalledWith({
      applied_count: 1,
      skipped_count: 2,
      latest_version_id: 'ver-1',
      latest_version_number: 2,
    }));
  });

  it('shows expired message and disables Apply button for expired sets', () => {
    render(
      <SuggestionBatchCard
        suggestionSet={expiredSet}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    // No accepted items → shows applySelected, which is disabled due to expired
    expect(screen.getByRole('button', { name: /applySelected/i })).toBeDisabled();
    expect(screen.getAllByText(/expired/i).length).toBeGreaterThan(0);
  });

  it('shows conflict banner on 409 and offers Regenerate', async () => {
    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-1/apply`, () =>
        HttpResponse.json({ error: { code: 'CONFLICT', message: 'Version conflict' } }, { status: 409 }),
      ),
    );
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/suggestion-sets`, () =>
        HttpResponse.json({ data: { set_id: 'batch-2' } }),
      ),
    );

    render(
      <SuggestionBatchCard
        suggestionSet={pendingSet}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /expand|batch/i }));
    await waitFor(() => expect(screen.getAllByRole('button', { name: /accept/i })[0]).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: /accept/i })[0]!);
    fireEvent.click(screen.getByRole('button', { name: /applyAccepted\(1\)/i }));

    await waitFor(() => expect(screen.getByText(/conflictBanner/i)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument();
  });
});
