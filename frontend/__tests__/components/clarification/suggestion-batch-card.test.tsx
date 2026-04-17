import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SuggestionBatchCard } from '@/components/clarification/suggestion-batch-card';
import type { SuggestionSet } from '@/lib/types/suggestion';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
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

  it('Apply Selected enabled after accepting at least one item', async () => {
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
    expect(screen.getByRole('button', { name: /applySelected/i })).not.toBeDisabled();
  });

  it('Apply Selected calls onApplied with accepted item IDs only', async () => {
    const onApplied = vi.fn();
    server.use(
      http.post(`${BASE}/api/v1/suggestion-sets/batch-1/apply`, async ({ request }) => {
        const body = await request.json() as { accepted_item_ids: string[] };
        expect(body.accepted_item_ids).toEqual(['item-1']);
        return HttpResponse.json({ data: { new_version: 2, applied_sections: ['acceptance_criteria'] } });
      }),
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

    // Accept only item-1
    fireEvent.click(screen.getAllByRole('button', { name: /accept/i })[0]!);
    // Reject item-2
    fireEvent.click(screen.getAllByRole('button', { name: /reject/i })[1]!);

    fireEvent.click(screen.getByRole('button', { name: /applySelected/i }));
    await waitFor(() => expect(onApplied).toHaveBeenCalledWith({ new_version: 2, applied_sections: ['acceptance_criteria'] }));
  });

  it('shows expired message and disables Apply Selected for expired sets', () => {
    render(
      <SuggestionBatchCard
        suggestionSet={expiredSet}
        onApplied={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
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
    fireEvent.click(screen.getByRole('button', { name: /applySelected/i }));

    await waitFor(() => expect(screen.getByText(/conflictBanner/i)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument();
  });
});
