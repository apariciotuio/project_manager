'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet } from '@/lib/api-client';

const POLL_INTERVAL_MS = 30_000;

interface UnreadCountResponse {
  data: { count: number };
}

interface UseUnreadCountResult {
  count: number;
  refetch: () => void;
  error: Error | null;
}

interface UseUnreadCountOptions {
  paused?: boolean;
}

export function useUnreadCount(options: UseUnreadCountOptions = {}): UseUnreadCountResult {
  const { paused = false } = options;
  const [count, setCount] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  // Trigger state used to force a re-fetch
  const [fetchTick, setFetchTick] = useState(0);

  const refetch = useCallback(() => {
    if (!paused) setFetchTick((t) => t + 1);
  }, [paused]);

  // Fetch on mount and on explicit refetch calls (skipped when paused)
  useEffect(() => {
    if (paused) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiGet<UnreadCountResponse>('/api/v1/notifications/unread-count');
        if (!cancelled) {
          setCount(res.data.count);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchTick, paused]);

  // 30s polling — pauses when document is hidden or DND is on
  useEffect(() => {
    if (paused) return;
    const interval = setInterval(() => {
      if (!document.hidden) {
        setFetchTick((t) => t + 1);
      }
    }, POLL_INTERVAL_MS);

    function onVisibilityChange() {
      if (!document.hidden) {
        // Became visible — fetch immediately
        setFetchTick((t) => t + 1);
      }
    }

    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [paused]);

  return { count, refetch, error };
}
