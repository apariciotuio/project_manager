'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPatch } from '@/lib/api-client';
import type { Section, SpecificationResponse } from '@/lib/types/work-item-detail';

interface UseSpecificationResult {
  sections: Section[];
  isLoading: boolean;
  error: Error | null;
  updateSection: (sectionId: string, content: string) => Promise<void>;
  refetch: () => void;
}

export function useSpecification(workItemId: string): UseSpecificationResult {
  const [sections, setSections] = useState<Section[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<SpecificationResponse>(
        `/api/v1/work-items/${workItemId}/specification`
      );
      setSections(res.data.sections);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const updateSection = useCallback(
    async (sectionId: string, content: string) => {
      // Optimistic update
      setSections((prev) =>
        prev.map((s) => (s.id === sectionId ? { ...s, content } : s))
      );
      try {
        const res = await apiPatch<{ data: Section }>(
          `/api/v1/work-items/${workItemId}/sections/${sectionId}`,
          { content }
        );
        setSections((prev) =>
          prev.map((s) => (s.id === sectionId ? res.data : s))
        );
      } catch (err) {
        // Roll back by re-fetching on failure
        void fetch();
        throw err;
      }
    },
    [workItemId, fetch]
  );

  return { sections, isLoading, error, updateSection, refetch: fetch };
}
