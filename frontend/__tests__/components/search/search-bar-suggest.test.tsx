/**
 * EP-13 — SearchBar suggest tests (Group 1).
 * Covers: 150ms debounce on suggest, dropdown renders ≤5 results,
 * keyboard nav (↑/↓/Enter), 503 shows unavailable banner.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SearchBar } from '@/components/search/search-bar';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));

// Also stub the search POST so SearchBar doesn't throw on unhandled request
function stubSearchPost() {
  server.use(
    http.post('http://localhost/api/v1/search', () =>
      HttpResponse.json({ data: { items: [], took_ms: 0, source: 'puppet', total: 0 } }),
    ),
  );
}

const SUGGEST_URL = 'http://localhost/api/v1/search/suggest';

function stubSuggest(results: Array<{ id: string; title: string; type: string }> = []) {
  server.use(
    http.get(SUGGEST_URL, () => HttpResponse.json({ data: results })),
  );
  stubSearchPost();
}

function stubSuggest503() {
  server.use(
    http.get(SUGGEST_URL, () =>
      HttpResponse.json({ error: { message: 'Service unavailable' } }, { status: 503 }),
    ),
  );
  stubSearchPost();
}

const MOCK_SUGGESTS = [
  { id: 's1', title: 'Fix login bug', type: 'work_item' },
  { id: 's2', title: 'Fix logout bug', type: 'work_item' },
  { id: 's3', title: 'Fix signup flow', type: 'work_item' },
];

afterEach(() => {
  vi.useRealTimers();
  server.resetHandlers();
});

describe('SearchBar — suggest dropdown', () => {
  it('does NOT call suggest API before 150ms debounce elapses', async () => {
    vi.useFakeTimers();
    let called = false;
    server.use(
      http.get(SUGGEST_URL, () => {
        called = true;
        return HttpResponse.json({ data: [] });
      }),
    );
    stubSearchPost();

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');

    input.focus();
    // Simulate typing without advancing timers
    await act(async () => {
      // Fire the change event directly to avoid userEvent delay issues with fake timers
      Object.defineProperty(input, 'value', { value: 'fi', writable: true, configurable: true });
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });

    // Advance timers to just before debounce
    act(() => { vi.advanceTimersByTime(100); });
    expect(called).toBe(false);

    vi.useRealTimers();
  });

  it('calls suggest API after 150ms debounce with ≥2 chars', async () => {
    // Use real timers — just verify the call happens within reasonable time
    let calledWith: string | null = null;
    server.use(
      http.get(SUGGEST_URL, ({ request }) => {
        calledWith = new URL(request.url).searchParams.get('q');
        return HttpResponse.json({ data: [] });
      }),
    );
    stubSearchPost();

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() => expect(calledWith).toBe('fix'), { timeout: 2000 });
  });

  it('renders suggest dropdown with up to 5 results', async () => {
    stubSuggest([
      ...MOCK_SUGGESTS,
      { id: 's4', title: 'Fix rate limit', type: 'work_item' },
      { id: 's5', title: 'Fix redirect', type: 'work_item' },
      { id: 's6', title: 'Fix websocket (should not appear)', type: 'work_item' },
    ]);

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() =>
      expect(screen.getByTestId('suggest-dropdown')).toBeInTheDocument(),
    );

    const items = screen.getAllByRole('option');
    expect(items).toHaveLength(5);
    expect(screen.queryByText('Fix websocket (should not appear)')).toBeNull();
  });

  it('does not render suggest dropdown when no results', async () => {
    stubSuggest([]);

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'xyz');

    // Wait for debounce to fire and response to arrive
    await waitFor(() => {
      expect(screen.queryByTestId('suggest-dropdown')).toBeNull();
    }, { timeout: 2000 });
  });

  it('keyboard ArrowDown selects first item', async () => {
    stubSuggest(MOCK_SUGGESTS);

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() =>
      expect(screen.getByTestId('suggest-dropdown')).toBeInTheDocument(),
    );

    await userEvent.keyboard('{ArrowDown}');

    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('keyboard ArrowUp from no selection wraps to last item', async () => {
    stubSuggest(MOCK_SUGGESTS);

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() =>
      expect(screen.getByTestId('suggest-dropdown')).toBeInTheDocument(),
    );

    await userEvent.keyboard('{ArrowUp}');

    const options = screen.getAllByRole('option');
    expect(options[options.length - 1]).toHaveAttribute('aria-selected', 'true');
  });

  it('Enter on a selected item navigates to its href', async () => {
    stubSuggest(MOCK_SUGGESTS);

    const assignSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { assign: assignSpy },
      writable: true,
      configurable: true,
    });

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() =>
      expect(screen.getByTestId('suggest-dropdown')).toBeInTheDocument(),
    );

    await userEvent.keyboard('{ArrowDown}');
    await userEvent.keyboard('{Enter}');

    expect(assignSpy).toHaveBeenCalledWith('/workspace/acme/items/s1');
  });

  it('shows search unavailable banner on 503', async () => {
    stubSuggest503();

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() =>
      expect(screen.getByTestId('search-unavailable-banner')).toBeInTheDocument(),
    );
  });

  it('Escape key closes suggest dropdown', async () => {
    stubSuggest(MOCK_SUGGESTS);

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'fix');

    await waitFor(() =>
      expect(screen.getByTestId('suggest-dropdown')).toBeInTheDocument(),
    );

    await userEvent.keyboard('{Escape}');

    expect(screen.queryByTestId('suggest-dropdown')).toBeNull();
  });

  it('suggest dropdown not shown for <2 chars', async () => {
    stubSuggest(MOCK_SUGGESTS);

    render(<SearchBar slug="acme" />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'f');

    // no dropdown should appear
    expect(screen.queryByTestId('suggest-dropdown')).toBeNull();
  });
});
