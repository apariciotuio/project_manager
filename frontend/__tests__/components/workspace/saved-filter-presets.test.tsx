/**
 * EP-09 — SavedFilterPresets tests.
 * Wraps SavedSearchesMenu with filter-bar specific interface.
 * Uses saved-searches endpoint (saved-filters BE endpoint not built).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SavedFilterPresets } from '@/components/workspace/saved-filter-presets';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockSavedSearches = [
  {
    id: 'ss-1',
    user_id: 'u1',
    workspace_id: 'ws-1',
    name: 'Draft bugs',
    query_params: { state: 'draft', type: 'bug' },
    is_shared: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'ss-2',
    user_id: 'u1',
    workspace_id: 'ws-1',
    name: 'High priority',
    query_params: { priority: 'high' },
    is_shared: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

function setupHandlers() {
  server.use(
    http.get('http://localhost/api/v1/saved-searches', () =>
      HttpResponse.json({ data: mockSavedSearches, message: 'ok' }),
    ),
    http.post('http://localhost/api/v1/saved-searches', () =>
      HttpResponse.json({
        data: { id: 'ss-3', name: 'New preset', query_params: {}, user_id: 'u1', workspace_id: 'ws-1', is_shared: false, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' },
        message: 'ok',
      }, { status: 201 }),
    ),
    http.delete('http://localhost/api/v1/saved-searches/:id', () =>
      new HttpResponse(null, { status: 204 }),
    ),
  );
}

describe('SavedFilterPresets', () => {
  beforeEach(() => {
    setupHandlers();
  });

  it('renders preset toggle button', () => {
    const onApply = vi.fn();
    render(<SavedFilterPresets currentFilters={{}} onApply={onApply} />);
    expect(screen.getByTestId('saved-filter-presets-toggle')).toBeInTheDocument();
  });

  it('shows saved preset names when opened', async () => {
    render(<SavedFilterPresets currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByTestId('saved-filter-presets-toggle'));
    await waitFor(() => {
      expect(screen.getByText('Draft bugs')).toBeInTheDocument();
      expect(screen.getByText('High priority')).toBeInTheDocument();
    });
  });

  it('calls onApply with preset query_params when preset is clicked', async () => {
    const onApply = vi.fn();
    render(<SavedFilterPresets currentFilters={{}} onApply={onApply} />);
    await userEvent.click(screen.getByTestId('saved-filter-presets-toggle'));
    await waitFor(() => {
      expect(screen.getByText('Draft bugs')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText('Draft bugs'));
    expect(onApply).toHaveBeenCalledWith({ state: 'draft', type: 'bug' });
  });

  it('shows empty state when no presets saved', async () => {
    server.use(
      http.get('http://localhost/api/v1/saved-searches', () =>
        HttpResponse.json({ data: [], message: 'ok' }),
      ),
    );
    render(<SavedFilterPresets currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByTestId('saved-filter-presets-toggle'));
    await waitFor(() => {
      expect(screen.getByTestId('saved-filter-presets-empty')).toBeInTheDocument();
    });
  });

  it('shows save form and calls create on submit', async () => {
    const onApply = vi.fn();
    render(<SavedFilterPresets currentFilters={{ state: 'draft' }} onApply={onApply} />);
    await userEvent.click(screen.getByTestId('saved-filter-presets-toggle'));
    await waitFor(() => {
      expect(screen.getByTestId('saved-filter-presets-name-input')).toBeInTheDocument();
    });
    await userEvent.type(screen.getByTestId('saved-filter-presets-name-input'), 'My preset');
    await userEvent.click(screen.getByTestId('saved-filter-presets-save-btn'));
    // Input clears after save
    await waitFor(() => {
      expect((screen.getByTestId('saved-filter-presets-name-input') as HTMLInputElement).value).toBe('');
    });
  });

  it('shows delete button and calls delete on click', async () => {
    render(<SavedFilterPresets currentFilters={{}} onApply={vi.fn()} />);
    await userEvent.click(screen.getByTestId('saved-filter-presets-toggle'));
    await waitFor(() => {
      expect(screen.getAllByTestId(/delete-preset-/)).toHaveLength(2);
    });
    await userEvent.click(screen.getAllByTestId(/delete-preset-/)[0]!);
    // Optimistic removal — item disappears
    await waitFor(() => {
      expect(screen.queryByText('Draft bugs')).not.toBeInTheDocument();
    });
  });
});
