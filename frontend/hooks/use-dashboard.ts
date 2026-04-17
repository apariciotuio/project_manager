'use client';

import { useState, useEffect } from 'react';
import { getWorkspaceDashboard } from '@/lib/api/dashboard';
import type { WorkspaceDashboard } from '@/lib/types/work-item';

interface UseDashboardResult {
  data: WorkspaceDashboard | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

/**
 * EP-09 — Dashboard data hook.
 * Polls every 300s (5min). Manual refresh via invalidate().
 */
export function useDashboard(): UseDashboardResult {
  const [data, setData] = useState<WorkspaceDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const result = await getWorkspaceDashboard();
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    // Poll every 300s
    const interval = setInterval(() => {
      if (!cancelled) setTick((t) => t + 1);
    }, 300_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [tick]);

  const refresh = () => setTick((t) => t + 1);

  return { data, isLoading, error, refresh };
}
