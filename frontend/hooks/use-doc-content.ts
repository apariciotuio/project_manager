'use client';

import { useState, useEffect } from 'react';
import { fetchDocContent } from '@/lib/api/docs';
import type { DocContent } from '@/lib/types/search';

interface UseDocContentResult {
  content: DocContent | null;
  isLoading: boolean;
  error: Error | null;
}

const cache = new Map<string, DocContent>();

export function useDocContent(docId: string | null): UseDocContentResult {
  const [content, setContent] = useState<DocContent | null>(docId ? (cache.get(docId) ?? null) : null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!docId) {
      setContent(null);
      setError(null);
      return;
    }

    const cached = cache.get(docId);
    if (cached) {
      setContent(cached);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    void (async () => {
      try {
        const res = await fetchDocContent(docId);
        if (!cancelled) {
          cache.set(docId, res.data);
          setContent(res.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setContent(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [docId]);

  return { content, isLoading, error };
}
