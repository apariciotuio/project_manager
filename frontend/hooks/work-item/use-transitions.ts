'use client';

import { useCallback, useEffect, useState } from 'react';
import { getTransitions } from '@/lib/api/work-items';
import type { StateTransitionRecord } from '@/lib/types/work-item';

interface UseTransitionsResult {
  transitions: StateTransitionRecord[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useTransitions(workItemId: string): UseTransitionsResult {
  const [transitions, setTransitions] = useState<StateTransitionRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setTransitions(await getTransitions(workItemId));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setTransitions([]);
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { transitions, isLoading, error, refetch: fetch };
}
