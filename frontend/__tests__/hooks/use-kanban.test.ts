/**
 * EP-09 — useKanbanBoard hook tests.
 *
 * Behaviour covered:
 *   - fetches board on mount and exposes data
 *   - isLoading flips true→false across the fetch
 *   - error state populated when the server errors
 *   - refetch re-requests the board
 *   - loadMoreColumn appends cards to the target column and updates its cursor
 *   - loadMoreColumn is a no-op when column has null next_cursor
 *   - loadingMoreColumns reflects per-column loading state
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({ useTranslations: () => (k: string) => k }));

const BASE = 'http://localhost';

const BOARD_PAGE_1 = {
  group_by: 'state',
  columns: [
    {
      key: 'draft',
      label: 'Draft',
      total_count: 3,
      cards: [
        { id: 'wi-1', title: 'One', type: 'task', state: 'draft', owner_id: null, completeness_score: 0, attachment_count: 0, tag_ids: [] },
        { id: 'wi-2', title: 'Two', type: 'task', state: 'draft', owner_id: null, completeness_score: 0, attachment_count: 0, tag_ids: [] },
      ],
      next_cursor: 'cursor-draft-2',
    },
    {
      key: 'ready',
      label: 'Ready',
      total_count: 1,
      cards: [
        { id: 'wi-3', title: 'Three', type: 'task', state: 'ready', owner_id: null, completeness_score: 100, attachment_count: 0, tag_ids: [] },
      ],
      next_cursor: null,
    },
  ],
};

const BOARD_DRAFT_PAGE_2 = {
  group_by: 'state',
  columns: [
    {
      key: 'draft',
      label: 'Draft',
      total_count: 3,
      cards: [
        { id: 'wi-4', title: 'Four', type: 'task', state: 'draft', owner_id: null, completeness_score: 0, attachment_count: 0, tag_ids: [] },
      ],
      next_cursor: null,
    },
  ],
};

describe('useKanbanBoard', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/kanban`, ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get('cursor_draft') === 'cursor-draft-2') {
          return HttpResponse.json({ data: BOARD_DRAFT_PAGE_2 });
        }
        return HttpResponse.json({ data: BOARD_PAGE_1 });
      }),
    );
  });

  it('fetches the board on mount and exposes data', async () => {
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data?.group_by).toBe('state');
    expect(result.current.data?.columns).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('flips isLoading true → false across the fetch', async () => {
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it('populates error state when the server errors', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/kanban`, () =>
        HttpResponse.json({ error: { code: 'INTERNAL', message: 'boom' } }, { status: 500 }),
      ),
    );
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.data).toBeNull();
  });

  it('refetch re-requests the board', async () => {
    let callCount = 0;
    server.use(
      http.get(`${BASE}/api/v1/work-items/kanban`, () => {
        callCount += 1;
        return HttpResponse.json({ data: BOARD_PAGE_1 });
      }),
    );
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(callCount).toBe(1);

    act(() => result.current.refetch());
    await waitFor(() => expect(callCount).toBe(2));
  });

  it('loadMoreColumn appends cards to the target column and updates next_cursor', async () => {
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data?.columns[0]!.cards).toHaveLength(2);

    act(() => result.current.loadMoreColumn('draft'));

    await waitFor(() => {
      const draft = result.current.data?.columns.find((c) => c.key === 'draft');
      expect(draft?.cards).toHaveLength(3);
    });
    const draft = result.current.data?.columns.find((c) => c.key === 'draft');
    expect(draft?.next_cursor).toBeNull();
    expect(draft?.cards.map((c) => c.id)).toEqual(['wi-1', 'wi-2', 'wi-4']);
  });

  it('loadMoreColumn is a no-op when column has null next_cursor', async () => {
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const readyBefore = result.current.data?.columns.find((c) => c.key === 'ready');
    expect(readyBefore?.next_cursor).toBeNull();

    act(() => result.current.loadMoreColumn('ready'));

    // No additional fetch; state stays stable.
    expect(result.current.loadingMoreColumns.has('ready')).toBe(false);
    const readyAfter = result.current.data?.columns.find((c) => c.key === 'ready');
    expect(readyAfter?.cards).toHaveLength(1);
  });

  it('loadMoreColumn is a no-op when board is not yet loaded', async () => {
    const { useKanbanBoard } = await import('@/hooks/use-kanban');
    const { result } = renderHook(() => useKanbanBoard({ group_by: 'state' }));

    // Fire before isLoading flips false — no cached board yet.
    act(() => result.current.loadMoreColumn('draft'));

    // Wait for initial fetch to settle; state survives.
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.loadingMoreColumns.size).toBe(0);
  });
});
