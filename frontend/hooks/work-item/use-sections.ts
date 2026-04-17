'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPatch } from '@/lib/api-client';
import type {
  Section,
  SectionUpdateRequest,
  SpecificationApiResponse,
  SectionUpdateResponse,
} from '@/lib/types/specification';

interface UseSectionsOptions {
  onPatchSuccess?: () => void;
}

interface UseSectionsResult {
  sections: Section[];
  isLoading: boolean;
  error: Error | null;
  patchSection: (sectionId: string, patch: SectionUpdateRequest) => Promise<void>;
  refetch: () => void;
}

export function useSections(
  workItemId: string,
  options: UseSectionsOptions = {}
): UseSectionsResult {
  const [sections, setSections] = useState<Section[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<SpecificationApiResponse>(
        `/api/v1/work-items/${workItemId}/specification`
      );
      setSections(res.data.sections);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setSections([]);
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const patchSection = useCallback(
    async (sectionId: string, patch: SectionUpdateRequest) => {
      // Optimistic update
      setSections((prev) =>
        prev.map((s) =>
          s.id === sectionId ? { ...s, content: patch.content } : s
        )
      );
      try {
        const res = await apiPatch<SectionUpdateResponse>(
          `/api/v1/work-items/${workItemId}/sections/${sectionId}`,
          patch
        );
        setSections((prev) =>
          prev.map((s) => (s.id === sectionId ? res.data : s))
        );
        options.onPatchSuccess?.();
      } catch (err) {
        // Roll back via refetch
        void fetch();
        throw err;
      }
    },
    [workItemId, fetch, options]
  );

  return { sections, isLoading, error, patchSection, refetch: fetch };
}
