'use client';

/**
 * EP-09 — useKanbanBoard hook.
 * Wraps getKanbanBoard with loading/error state and per-column load-more.
 */
import { useEffect, useState, useCallback } from 'react';
import { getKanbanBoard } from '@/lib/api/kanban';
import type { KanbanBoard, KanbanFilters, KanbanColumn, KanbanCard } from '@/lib/api/kanban';

interface UseKanbanResult {
  data: KanbanBoard | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  loadMoreColumn: (columnKey: string) => void;
  loadingMoreColumns: Set<string>;
}

export function useKanbanBoard(filters: KanbanFilters = {}): UseKanbanResult {
  const [data, setData] = useState<KanbanBoard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);
  const [loadingMoreColumns, setLoadingMoreColumns] = useState<Set<string>>(new Set());

  const filtersKey = JSON.stringify(filters);
  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const board = await getKanbanBoard(filters);
        if (!cancelled) setData(board);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey, tick]);

  const loadMoreColumn = useCallback((columnKey: string) => {
    if (!data) return;
    const col = data.columns.find((c) => c.key === columnKey);
    if (!col?.next_cursor) return;

    setLoadingMoreColumns((prev) => new Set([...prev, columnKey]));
    void (async () => {
      try {
        const next = await getKanbanBoard({ ...filters, [`cursor_${columnKey}`]: col.next_cursor } as KanbanFilters);
        const nextCol = next.columns.find((c) => c.key === columnKey);
        if (!nextCol) return;
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            columns: prev.columns.map((c): KanbanColumn =>
              c.key === columnKey
                ? {
                    ...c,
                    cards: [...c.cards, ...nextCol.cards] as KanbanCard[],
                    next_cursor: nextCol.next_cursor,
                  }
                : c,
            ),
          };
        });
      } finally {
        setLoadingMoreColumns((prev) => {
          const next = new Set(prev);
          next.delete(columnKey);
          return next;
        });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, filtersKey]);

  return { data, isLoading, error, refetch, loadMoreColumn, loadingMoreColumns };
}
