'use client';

import { useState, useEffect, useCallback } from 'react';
import { getReadyGate } from '@/lib/api/ready-gate';
import type { ReadyGateResult } from '@/lib/api/ready-gate';

interface UseReadyGateResult {
  gate: ReadyGateResult | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useReadyGate(workItemId: string): UseReadyGateResult {
  const [gate, setGate] = useState<ReadyGateResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getReadyGate(workItemId);
      setGate(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { gate, isLoading, error, refetch };
}
