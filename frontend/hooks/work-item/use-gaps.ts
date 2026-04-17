'use client';

import { useState, useEffect, useCallback } from 'react';
import { getGapReport, triggerAiReview } from '@/lib/api/gaps';
import type { GapReport } from '@/lib/types/gap';

interface UseGapsResult {
  gapReport: GapReport | null;
  isLoading: boolean;
  error: Error | null;
  isReviewing: boolean;
  refetch: () => void;
  runAiReview: () => Promise<void>;
}

export function useGaps(workItemId: string): UseGapsResult {
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [isReviewing, setIsReviewing] = useState(false);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const report = await getGapReport(workItemId);
      setGapReport(report);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const runAiReview = useCallback(async () => {
    setIsReviewing(true);
    try {
      await triggerAiReview(workItemId);
      // Poll for updated findings after triggering; EP-08 SSE not yet wired
      await new Promise<void>((resolve) => setTimeout(resolve, 3000));
      await fetch();
    } finally {
      setIsReviewing(false);
    }
  }, [workItemId, fetch]);

  return {
    gapReport,
    isLoading,
    error,
    isReviewing,
    refetch: fetch,
    runAiReview,
  };
}
