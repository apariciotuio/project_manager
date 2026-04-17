'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';
import type { NextStepResult, NextStepApiResponse } from '@/lib/types/specification';

interface UseNextStepResult {
  nextStep: NextStepResult | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useNextStep(workItemId: string): UseNextStepResult {
  const [nextStep, setNextStep] = useState<NextStepResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<NextStepApiResponse>(
        `/api/v1/work-items/${workItemId}/next-step`
      );
      setNextStep(res.data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setNextStep(null);
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { nextStep, isLoading, error, refetch: fetch };
}
