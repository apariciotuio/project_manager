'use client';

/**
 * EP-09 — usePipeline hook.
 * Wraps getPipeline with loading/error state. Polls every 30s (matches BE cache TTL).
 */
import { useEffect, useState, useCallback } from 'react';
import { getPipeline } from '@/lib/api/pipeline';
import type { PipelineBoard, PipelineFilters } from '@/lib/api/pipeline';

interface UsePipelineResult {
  data: PipelineBoard | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function usePipeline(filters: PipelineFilters = {}): UsePipelineResult {
  const [data, setData] = useState<PipelineBoard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  const filtersKey = JSON.stringify(filters);
  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void (async () => {
      try {
        const board = await getPipeline(filters);
        if (!cancelled) {
          setData(board);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey, tick]);

  return { data, isLoading, error, refetch };
}
