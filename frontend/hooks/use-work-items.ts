'use client';

import { useEffect, useState, useCallback } from 'react';
import { listWorkItems } from '@/lib/api/work-items';
import type { WorkItemResponse, WorkItemFilters } from '@/lib/types/work-item';

interface UseWorkItemsResult {
  items: WorkItemResponse[];
  total: number;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  // EP-09 cursor-based load more
  hasNext: boolean;
  isLoadingMore: boolean;
  loadMore: () => void;
}

export function useWorkItems(
  projectId: string | null,
  filters: WorkItemFilters,
): UseWorkItemsResult {
  const [items, setItems] = useState<WorkItemResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(projectId !== null);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  // Cursor state
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasNext, setHasNext] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const filtersKey = JSON.stringify(filters);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  // Reset cursor when filters change
  useEffect(() => {
    setCursor(null);
    setHasNext(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const res = await listWorkItems(projectId, filters);
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
          setCursor(res.cursor ?? null);
          setHasNext(res.has_next ?? false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setItems([]);
          setTotal(0);
          setCursor(null);
          setHasNext(false);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, filtersKey, tick]);

  const loadMore = useCallback(() => {
    if (!projectId || !cursor || isLoadingMore) return;
    let cancelled = false;
    setIsLoadingMore(true);
    void (async () => {
      try {
        const res = await listWorkItems(projectId, { ...filters, cursor });
        if (!cancelled) {
          setItems((prev) => [...prev, ...res.items]);
          setTotal(res.total);
          setCursor(res.cursor ?? null);
          setHasNext(res.has_next ?? false);
        }
      } catch {
        // non-fatal — keep existing items
      } finally {
        if (!cancelled) setIsLoadingMore(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, cursor, isLoadingMore, filtersKey]);

  return { items, total, isLoading, error, refetch, hasNext, isLoadingMore, loadMore };
}
