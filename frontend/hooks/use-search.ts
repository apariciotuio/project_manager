'use client';

import { useState, useEffect, useRef } from 'react';
import { searchWorkItems } from '@/lib/api/search';
import type { SearchResult } from '@/lib/types/work-item';

const DEBOUNCE_MS = 300;
const MIN_CHARS = 2;

interface UseSearchResult {
  data: SearchResult | null;
  isLoading: boolean;
  error: Error | null;
  isActive: boolean;
}

/**
 * EP-09 — debounced search hook.
 * Fires POST /api/v1/search only when query.length >= 2, after 300ms debounce.
 */
export function useSearch(query: string, limit = 20): UseSearchResult {
  const [data, setData] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isActive = query.length >= MIN_CHARS;

  useEffect(() => {
    // Clear any pending timer
    if (timerRef.current) clearTimeout(timerRef.current);

    if (!isActive) {
      setData(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    timerRef.current = setTimeout(() => {
      let cancelled = false;
      void (async () => {
        try {
          const result = await searchWorkItems({ q: query, limit });
          if (!cancelled) {
            setData(result);
            setError(null);
          }
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err : new Error(String(err)));
            setData(null);
          }
        } finally {
          if (!cancelled) setIsLoading(false);
        }
      })();
      return () => { cancelled = true; };
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, limit]);

  return { data, isLoading, error, isActive };
}
