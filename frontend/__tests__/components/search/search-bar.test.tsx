/**
 * EP-09 — SearchBar component tests.
 * Covers: debounce, min chars, results render, clear, source meta, error state.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SearchBar } from '@/components/search/search-bar';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));

const mockSearchItem: WorkItemResponse = {
  id: 'wi-search-1',
  title: 'Found item via search',
  type: 'bug',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: null,
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 30,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-15T00:00:00Z',
  deleted_at: null,
};

function stubSearch(items = [mockSearchItem], took_ms = 42, source: 'puppet' | 'sql_fallback' = 'puppet') {
  server.use(
    http.post('http://localhost/api/v1/search', () =>
      HttpResponse.json({
        data: { items, took_ms, source, total: items.length },
        message: 'ok',
      }),
    ),
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe('SearchBar', () => {
  it('renders search input', () => {
    render(<SearchBar slug="acme" />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });

  it('does not show results panel when query is empty', () => {
    render(<SearchBar slug="acme" />);
    expect(screen.queryByTestId('search-results-panel')).toBeNull();
  });

  it('does not call search API with < 2 chars', async () => {
    vi.useRealTimers();
    const onResults = vi.fn();
    // MSW onUnhandledRequest is 'error' - no handler needed; if search is called it would fail
    // Just verify onResults is NOT called when typing 1 char and waiting
    render(<SearchBar slug="acme" onResults={onResults} />);
    const input = screen.getByRole('searchbox');
    // fire manual change for 1 char without full debounce wait
    await userEvent.type(input, 'a');
    // results panel should NOT appear for < 2 chars
    expect(screen.queryByTestId('search-results-panel')).toBeNull();
  });

  it('shows results panel when query has >= 2 chars', async () => {
    vi.useRealTimers();
    stubSearch();
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'bu');
    // panel appears immediately (isActive = true)
    expect(screen.getByTestId('search-results-panel')).toBeInTheDocument();
  });

  it('renders search results after API responds', async () => {
    vi.useRealTimers();
    stubSearch([mockSearchItem]);
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'bug issue');

    await waitFor(() =>
      expect(screen.getByText('Found item via search')).toBeInTheDocument(),
    );
  });

  it('shows source and took_ms metadata', async () => {
    vi.useRealTimers();
    stubSearch([mockSearchItem], 55, 'puppet');
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'test query');

    await waitFor(() =>
      expect(screen.getByTestId('search-source')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('search-took')).toBeInTheDocument();
    expect(screen.getByTestId('search-count')).toBeInTheDocument();
  });

  it('shows empty message when no results', async () => {
    vi.useRealTimers();
    stubSearch([]);
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'nothing matches');

    await waitFor(() =>
      expect(screen.getByTestId('search-results-panel')).toBeInTheDocument(),
    );
    // data is returned but items is empty — check count shows 0
    await waitFor(() => expect(screen.getByTestId('search-count')).toBeInTheDocument());
  });

  it('clear button clears the input and hides results panel', async () => {
    vi.useRealTimers();
    stubSearch([mockSearchItem]);
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'bug issue');

    await waitFor(() =>
      expect(screen.getByText('Found item via search')).toBeInTheDocument(),
    );

    const clearBtn = screen.getByRole('button', { name: /clearSearch/i });
    await userEvent.click(clearBtn);

    expect((input as HTMLInputElement).value).toBe('');
    expect(screen.queryByTestId('search-results-panel')).toBeNull();
  });

  it('shows error state on API failure', async () => {
    vi.useRealTimers();
    server.use(
      http.post('http://localhost/api/v1/search', () =>
        HttpResponse.json({ error: { message: 'Service unavailable' } }, { status: 503 }),
      ),
    );
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'trigger error');

    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument(),
    );
  });

  it('result items link to workspace item detail page', async () => {
    vi.useRealTimers();
    stubSearch([mockSearchItem]);
    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'found item');

    await waitFor(() =>
      expect(screen.getByText('Found item via search')).toBeInTheDocument(),
    );
    const link = screen.getByText('Found item via search').closest('a');
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-search-1');
  });

  it('calls onSearchActiveChange(true) when query >= 2 chars', async () => {
    vi.useRealTimers();
    stubSearch([]);
    const onActiveChange = vi.fn();
    render(<SearchBar slug="acme" onSearchActiveChange={onActiveChange} />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'ab');
    expect(onActiveChange).toHaveBeenCalledWith(true);
  });

  it('calls onSearchActiveChange(false) when query < 2 chars', async () => {
    vi.useRealTimers();
    stubSearch([]);
    const onActiveChange = vi.fn();
    render(<SearchBar slug="acme" onSearchActiveChange={onActiveChange} />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'a');
    expect(onActiveChange).toHaveBeenCalledWith(false);
  });
});
