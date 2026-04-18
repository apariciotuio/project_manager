'use client';

import { useState, useEffect, useCallback } from 'react';
import { listVersions, diffVsPrevious } from '@/lib/api/versions';
import type { WorkItemVersionSummary, VersionDiff } from '@/lib/api/versions';
import { ApiError } from '@/lib/api-client';

interface UseVersionsResult {
  versions: WorkItemVersionSummary[];
  isLoading: boolean;
  error: Error | null;
  hasMore: boolean;
  loadMore: () => Promise<void>;
  refetch: () => Promise<void>;
}

export function useVersions(workItemId: string): UseVersionsResult {
  const [versions, setVersions] = useState<WorkItemVersionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [cursor, setCursor] = useState<number | undefined>(undefined);

  const fetchPage = useCallback(
    async (beforeCursor?: number, reset = false) => {
      setIsLoading(true);
      setError(null);
      try {
        const page = await listVersions(workItemId, beforeCursor);
        setVersions((prev) => (reset ? page.data : [...prev, ...page.data]));
        setHasMore(page.meta.has_more);
        if (page.meta.next_cursor !== null) {
          setCursor(Number(page.meta.next_cursor));
        } else {
          setCursor(undefined);
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to load versions'));
      } finally {
        setIsLoading(false);
      }
    },
    [workItemId],
  );

  useEffect(() => {
    void fetchPage(undefined, true);
  }, [fetchPage]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoading) return;
    await fetchPage(cursor);
  }, [cursor, fetchPage, hasMore, isLoading]);

  const refetch = useCallback(async () => {
    setCursor(undefined);
    await fetchPage(undefined, true);
  }, [fetchPage]);

  return { versions, isLoading, error, hasMore, loadMore, refetch };
}

interface UseDiffResult {
  diff: VersionDiff | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useDiffVsPrevious(
  workItemId: string,
  versionNumber: number | null,
): UseDiffResult {
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    if (versionNumber === null) return;
    setIsLoading(true);
    setError(null);
    diffVsPrevious(workItemId, versionNumber)
      .then((d) => setDiff(d))
      .catch((err) => setError(err instanceof Error ? err : new Error('Failed to load diff')))
      .finally(() => setIsLoading(false));
  }, [workItemId, versionNumber, retryNonce]);

  const refetch = useCallback(() => {
    setRetryNonce((n) => n + 1);
  }, []);

  return { diff, isLoading, error, refetch };
}

export function useVersionDiff(
  workItemId: string,
  fromVersion: number,
  toVersion: number,
): UseDiffResult {
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (fromVersion >= toVersion) {
      setDiff(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    import('@/lib/api/versions')
      .then(({ getArbitraryDiff }) => getArbitraryDiff(workItemId, fromVersion, toVersion))
      .then((d) => setDiff(d))
      .catch((err) => setError(err instanceof Error ? err : new Error('Failed to load diff')))
      .finally(() => setIsLoading(false));
  }, [workItemId, fromVersion, toVersion]);

  return { diff, isLoading, error };
}
