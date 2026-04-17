'use client';

import { useCallback, useState } from 'react';
import { transitionState } from '@/lib/api/work-items';
import type { WorkItemResponse, WorkItemState } from '@/lib/types/work-item';

interface UseTransitionStateResult {
  transition: (target_state: WorkItemState, reason?: string) => Promise<WorkItemResponse | null>;
  isPending: boolean;
  error: Error | null;
}

export function useTransitionState(workItemId: string): UseTransitionStateResult {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const transition = useCallback(
    async (
      target_state: WorkItemState,
      reason?: string,
    ): Promise<WorkItemResponse | null> => {
      setIsPending(true);
      setError(null);
      try {
        const body = reason === undefined ? { target_state } : { target_state, reason };
        const result = await transitionState(workItemId, body);
        return result;
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        return null;
      } finally {
        setIsPending(false);
      }
    },
    [workItemId],
  );

  return { transition, isPending, error };
}
