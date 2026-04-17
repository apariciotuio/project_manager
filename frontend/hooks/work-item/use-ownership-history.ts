'use client';

import { useCallback, useEffect, useState } from 'react';
import { getOwnershipHistory } from '@/lib/api/work-items';
import type { OwnershipRecord } from '@/lib/types/work-item';

interface UseOwnershipHistoryResult {
  history: OwnershipRecord[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useOwnershipHistory(workItemId: string): UseOwnershipHistoryResult {
  const [history, setHistory] = useState<OwnershipRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setHistory(await getOwnershipHistory(workItemId));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setHistory([]);
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { history, isLoading, error, refetch: fetch };
}
