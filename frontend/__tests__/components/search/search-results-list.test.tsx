import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SearchResultsList } from '@/components/search/search-results-list';
import type { PuppetSearchResult, PuppetSearchResponse } from '@/lib/types/search';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));

const makeResult = (id: string, entity_type: PuppetSearchResult['entity_type'] = 'work_item'): PuppetSearchResult => ({
  id,
  entity_type,
  title: `Item ${id}`,
  type: entity_type === 'work_item' ? 'bug' : undefined,
  state: entity_type === 'work_item' ? 'draft' : undefined,
  score: 0.9,
  snippet: `Snippet for ${id}`,
  workspace_id: 'ws-1',
});

const makeResponse = (results: PuppetSearchResult[], has_next = false): PuppetSearchResponse => ({
  data: results,
  pagination: { cursor: has_next ? 'next-cursor' : null, has_next },
  meta: { puppet_latency_ms: 45 },
});

describe('SearchResultsList', () => {
  it('renders skeleton cards when isLoading is true', () => {
    render(
      <SearchResultsList
        response={null}
        isLoading={true}
        error={null}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId('search-result-skeleton')).toHaveLength(3);
  });

  it('renders empty state when results are empty', () => {
    render(
      <SearchResultsList
        response={makeResponse([])}
        isLoading={false}
        error={null}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.getByTestId('search-empty-state')).toBeInTheDocument();
  });

  it('renders SearchResultCard for work_item entity type', () => {
    const response = makeResponse([makeResult('wi-1', 'work_item')]);
    render(
      <SearchResultsList
        response={response}
        isLoading={false}
        error={null}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.getByText('Item wi-1')).toBeInTheDocument();
  });

  it('renders DocResultCard for doc entity type', () => {
    const response = makeResponse([makeResult('doc-1', 'doc')]);
    render(
      <SearchResultsList
        response={response}
        isLoading={false}
        error={null}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.getByTestId('entity-type-badge')).toBeInTheDocument();
  });

  it('shows error banner on 503 (upstream unavailable)', () => {
    const err = new Error('Service unavailable');
    render(
      <SearchResultsList
        response={null}
        isLoading={false}
        error={err}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows Load More button when has_next is true', () => {
    const response = makeResponse([makeResult('wi-1')], true);
    render(
      <SearchResultsList
        response={response}
        isLoading={false}
        error={null}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /loadMore/i })).toBeInTheDocument();
  });

  it('does not show Load More when has_next is false', () => {
    const response = makeResponse([makeResult('wi-1')], false);
    render(
      <SearchResultsList
        response={response}
        isLoading={false}
        error={null}
        slug="acme"
        onLoadMore={vi.fn()}
        onDocPreview={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: /loadMore/i })).not.toBeInTheDocument();
  });
});
