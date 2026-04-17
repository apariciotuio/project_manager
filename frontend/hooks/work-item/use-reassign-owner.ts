'use client';

import { useCallback, useState } from 'react';
import { reassignOwner } from '@/lib/api/work-items';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface UseReassignOwnerResult {
  reassign: (new_owner_id: string, reason?: string) => Promise<WorkItemResponse | null>;
  isPending: boolean;
  error: Error | null;
}

export function useReassignOwner(workItemId: string): UseReassignOwnerResult {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const reassign = useCallback(
    async (new_owner_id: string, reason?: string): Promise<WorkItemResponse | null> => {
      setIsPending(true);
      setError(null);
      try {
        const body =
          reason === undefined ? { new_owner_id } : { new_owner_id, reason };
        return await reassignOwner(workItemId, body);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        return null;
      } finally {
        setIsPending(false);
      }
    },
    [workItemId],
  );

  return { reassign, isPending, error };
}
