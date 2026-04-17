'use client';

import { useCallback, useState } from 'react';
import { forceReady as forceReadyApi } from '@/lib/api/work-items';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface UseForceReadyResult {
  forceReady: (justification: string) => Promise<WorkItemResponse | null>;
  isPending: boolean;
  error: Error | null;
}

export function useForceReady(workItemId: string): UseForceReadyResult {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const forceReady = useCallback(
    async (justification: string): Promise<WorkItemResponse | null> => {
      setIsPending(true);
      setError(null);
      try {
        return await forceReadyApi(workItemId, { justification, confirmed: true });
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        return null;
      } finally {
        setIsPending(false);
      }
    },
    [workItemId],
  );

  return { forceReady, isPending, error };
}
