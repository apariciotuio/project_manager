/**
 * EP-09 — SavedSearchesMenu component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SavedSearchesMenu } from '@/components/search/saved-searches-menu';
import type { SavedSearch } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));

const mockSearch: SavedSearch = {
  id: 'ss-1',
  user_id: 'user-1',
  workspace_id: 'ws-1',
  name: 'My bugs',
  query_params: { state: 'draft', type: 'bug' },
  is_shared: false,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

function stubList(items: SavedSearch[] = [mockSearch]) {
  server.use(
    http.get('http://localhost/api/v1/saved-searches', () =>
      HttpResponse.json({ data: items, message: 'ok' }),
    ),
  );
}

function stubCreate(result: SavedSearch = mockSearch) {
  server.use(
    http.post('http://localhost/api/v1/saved-searches', () =>
      HttpResponse.json({ data: result, message: 'saved search created' }, { status: 201 }),
    ),
  );
}

function stubDelete(id: string) {
  server.use(
    http.delete(`http://localhost/api/v1/saved-searches/${id}`, () =>
      new HttpResponse(null, { status: 204 }),
    ),
  );
}

describe('SavedSearchesMenu', () => {
  it('renders toggle button', () => {
    stubList();
    render(<SavedSearchesMenu currentFilters={{}} onApply={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'title' })).toBeInTheDocument();
  });

  it('opens dropdown on button click', async () => {
    stubList([]);
    render(<SavedSearchesMenu currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));
    expect(screen.getByRole('dialog', { name: 'title' })).toBeInTheDocument();
  });

  it('shows list of saved searches after load', async () => {
    stubList([mockSearch]);
    render(<SavedSearchesMenu currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));
    await waitFor(() => expect(screen.getByText('My bugs')).toBeInTheDocument());
  });

  it('shows empty state when no saved searches', async () => {
    stubList([]);
    render(<SavedSearchesMenu currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));
    await waitFor(() => expect(screen.getByText('empty')).toBeInTheDocument());
  });

  it('clicking a saved search calls onApply with its query_params', async () => {
    stubList([mockSearch]);
    const onApply = vi.fn();
    render(<SavedSearchesMenu currentFilters={{}} onApply={onApply} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));
    await waitFor(() => expect(screen.getByText('My bugs')).toBeInTheDocument());

    const applyBtn = screen.getByRole('button', { name: /applyAria/i });
    await userEvent.click(applyBtn);
    expect(onApply).toHaveBeenCalledWith(mockSearch.query_params);
  });

  it('save name input submits and adds to list', async () => {
    stubList([]);
    const newSearch: SavedSearch = { ...mockSearch, id: 'ss-new', name: 'New search' };
    stubCreate(newSearch);
    render(<SavedSearchesMenu currentFilters={{ state: 'draft' }} onApply={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));

    const input = screen.getByRole('textbox', { name: 'namePlaceholder' });
    await userEvent.type(input, 'New search');
    await userEvent.click(screen.getByRole('button', { name: 'saveConfirm' }));

    await waitFor(() => expect(screen.getByText('New search')).toBeInTheDocument());
  });

  it('delete button optimistically removes saved search from list', async () => {
    stubList([mockSearch]);
    stubDelete(mockSearch.id);
    render(<SavedSearchesMenu currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));
    await waitFor(() => expect(screen.getByText('My bugs')).toBeInTheDocument());

    const deleteBtn = screen.getByRole('button', { name: /deleteAria/i });
    await userEvent.click(deleteBtn);

    // Optimistic: item removed immediately from local state
    await waitFor(() => expect(screen.queryByText('My bugs')).toBeNull());
  });

  it('shows error when load fails', async () => {
    server.use(
      http.get('http://localhost/api/v1/saved-searches', () =>
        HttpResponse.json({ error: { message: 'Unauthorized' } }, { status: 401 }),
      ),
    );
    render(<SavedSearchesMenu currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'title' }));
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument(),
    );
  });
});
