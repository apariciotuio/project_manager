'use client';

/**
 * EP-09 — usePersonDashboard hook.
 */
import { useEffect, useState, useCallback } from 'react';
import { getPersonDashboard } from '@/lib/api/dashboard';
import { ApiError } from '@/lib/types/auth';
import type { PersonDashboard } from '@/lib/api/dashboard';

interface UsePersonDashboardResult {
  data: PersonDashboard | null;
  isLoading: boolean;
  error: Error | null;
  isForbidden: boolean;
  refetch: () => void;
}

export function usePersonDashboard(userId: string): UsePersonDashboardResult {
  const [data, setData] = useState<PersonDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setIsForbidden(false);
    void (async () => {
      try {
        const result = await getPersonDashboard(userId);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 403) {
            setIsForbidden(true);
          } else {
            setError(err instanceof Error ? err : new Error(String(err)));
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [userId, tick]);

  return { data, isLoading, error, isForbidden, refetch };
}
