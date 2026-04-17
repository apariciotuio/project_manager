'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';
import type { CompletenessData, CompletenessResponse } from '@/lib/types/work-item-detail';

interface UseCompletenessResult {
  completeness: CompletenessData | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useCompleteness(workItemId: string): UseCompletenessResult {
  const [completeness, setCompleteness] = useState<CompletenessData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<CompletenessResponse>(
        `/api/v1/work-items/${workItemId}/completeness`
      );
      setCompleteness(res.data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setCompleteness(null);
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { completeness, isLoading, error, refetch: fetch };
}
