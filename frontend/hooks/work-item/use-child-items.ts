'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';
import type { WorkItemResponse, PagedWorkItemResponse } from '@/lib/types/work-item';

interface UseChildItemsResult {
  children: WorkItemResponse[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useChildItems(workItemId: string): UseChildItemsResult {
  const [children, setChildren] = useState<WorkItemResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<{ data: PagedWorkItemResponse<WorkItemResponse> }>(
        `/api/v1/work-items?parent_work_item_id=${workItemId}&page_size=50`
      );
      setChildren(res.data.items);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { children, isLoading, error, refetch: fetch };
}
