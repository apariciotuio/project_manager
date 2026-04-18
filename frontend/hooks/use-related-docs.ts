'use client';

import { useState, useEffect } from 'react';
import { fetchRelatedDocs } from '@/lib/api/docs';
import type { RelatedDoc } from '@/lib/types/search';

interface UseRelatedDocsResult {
  docs: RelatedDoc[];
  isLoading: boolean;
  error: Error | null;
}

export function useRelatedDocs(workItemId: string | null): UseRelatedDocsResult {
  const [docs, setDocs] = useState<RelatedDoc[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!workItemId) {
      setDocs([]);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    void (async () => {
      try {
        const res = await fetchRelatedDocs(workItemId);
        if (!cancelled) {
          setDocs(res.data.slice(0, 5));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setDocs([]);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [workItemId]);

  return { docs, isLoading, error };
}
