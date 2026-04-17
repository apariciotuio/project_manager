'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface UseWorkItemResult {
  workItem: WorkItemResponse | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useWorkItem(id: string): UseWorkItemResult {
  const [workItem, setWorkItem] = useState<WorkItemResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<{ data: WorkItemResponse }>(`/api/v1/work-items/${id}`);
      setWorkItem(res.data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setWorkItem(null);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { workItem, isLoading, error, refetch: fetch };
}
