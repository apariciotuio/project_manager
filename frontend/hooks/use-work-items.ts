'use client';

import { useEffect, useState } from 'react';
import { listWorkItems } from '@/lib/api/work-items';
import type { WorkItemResponse, WorkItemFilters } from '@/lib/types/work-item';

interface UseWorkItemsResult {
  items: WorkItemResponse[];
  total: number;
  isLoading: boolean;
  error: Error | null;
}

export function useWorkItems(
  projectId: string | null,
  filters: WorkItemFilters,
): UseWorkItemsResult {
  const [items, setItems] = useState<WorkItemResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(projectId !== null);
  const [error, setError] = useState<Error | null>(null);

  const filtersKey = JSON.stringify(filters);

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
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setItems([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, filtersKey]);

  return { items, total, isLoading, error };
}
