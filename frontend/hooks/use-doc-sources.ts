'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet, apiPost, apiDelete } from '@/lib/api-client';
import type {
  DocSource,
  DocSourceCreate,
  DocSourceListResponse,
  DocSourceResponse,
} from '@/lib/types/puppet';

const POLLING_INTERVAL_MS = 5000;

interface UseDocSourcesResult {
  sources: DocSource[];
  isLoading: boolean;
  error: Error | null;
  hasPolling: boolean;
  addSource: (req: DocSourceCreate) => Promise<DocSource>;
  removeSource: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useDocSources(): UseDocSourcesResult {
  const [sources, setSources] = useState<DocSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const hasPolling = sources.some((s) => s.status === 'pending' || s.status === 'indexing');

  const fetchSources = useCallback(async (initial = false): Promise<void> => {
    if (initial) setIsLoading(true);
    try {
      const res = await apiGet<DocSourceListResponse>('/api/v1/admin/documentation-sources');
      setSources(res.data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      if (initial) setIsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    void fetchSources(true);
  }, [fetchSources]);

  // Polling when any source is pending/indexing
  useEffect(() => {
    if (!hasPolling) return;

    pollingTimerRef.current = setInterval(() => {
      void fetchSources(false);
    }, POLLING_INTERVAL_MS);

    return () => {
      if (pollingTimerRef.current !== null) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, [hasPolling, fetchSources]);

  const addSource = useCallback(async (req: DocSourceCreate): Promise<DocSource> => {
    const res = await apiPost<DocSourceResponse>('/api/v1/admin/documentation-sources', req);
    setSources((prev) => [res.data, ...prev]);
    return res.data;
  }, []);

  const removeSource = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/v1/admin/documentation-sources/${id}`);
    setSources((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const refresh = useCallback(() => fetchSources(false), [fetchSources]);

  return { sources, isLoading, error, hasPolling, addSource, removeSource, refresh };
}
