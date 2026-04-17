'use client';

import { useState, useEffect, useCallback } from 'react';
import { getValidations, waiveValidation } from '@/lib/api/validations';
import type { ValidationChecklist } from '@/lib/api/validations';

interface UseValidationsResult {
  checklist: ValidationChecklist | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  waive: (ruleId: string) => Promise<void>;
}

const EMPTY: ValidationChecklist = { required: [], recommended: [] };

export function useValidations(workItemId: string): UseValidationsResult {
  const [checklist, setChecklist] = useState<ValidationChecklist | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getValidations(workItemId);
      setChecklist(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const waive = useCallback(
    async (ruleId: string) => {
      // Optimistic update
      setChecklist((prev) => {
        if (!prev) return prev;
        const updateRule = (rules: ValidationChecklist['recommended']) =>
          rules.map((r) =>
            r.rule_id === ruleId ? { ...r, status: 'waived' as const } : r,
          );
        return {
          required: updateRule(prev.required),
          recommended: updateRule(prev.recommended),
        };
      });
      try {
        await waiveValidation(workItemId, ruleId);
        await refetch();
      } catch (err) {
        // Roll back by refetching
        await refetch();
        throw err;
      }
    },
    [workItemId, refetch],
  );

  return { checklist: checklist ?? EMPTY, isLoading, error, refetch, waive };
}
