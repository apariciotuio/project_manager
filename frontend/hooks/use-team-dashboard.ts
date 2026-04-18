'use client';

/**
 * EP-09 — useTeamDashboard hook.
 */
import { useEffect, useState, useCallback } from 'react';
import { getTeamDashboard } from '@/lib/api/dashboard';
import type { TeamDashboard } from '@/lib/api/dashboard';

interface UseTeamDashboardResult {
  data: TeamDashboard | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useTeamDashboard(teamId: string): UseTeamDashboardResult {
  const [data, setData] = useState<TeamDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const result = await getTeamDashboard(teamId);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [teamId, tick]);

  return { data, isLoading, error, refetch };
}
