'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';
import type { TimelineEvent, TimelineResponse } from '@/lib/types/work-item-detail';

const PAGE_SIZE = 20;

interface UseTimelineResult {
  events: TimelineEvent[];
  isLoading: boolean;
  error: Error | null;
  hasMore: boolean;
  loadMore: () => void;
  refetch: () => void;
}

export function useTimeline(workItemId: string): UseTimelineResult {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (cursorValue: string | null, append: boolean) => {
      setIsLoading(true);
      setError(null);
      try {
        const qs = cursorValue
          ? `?cursor=${encodeURIComponent(cursorValue)}&limit=${PAGE_SIZE}`
          : `?limit=${PAGE_SIZE}`;
        const res = await apiGet<TimelineResponse>(
          `/api/v1/work-items/${workItemId}/timeline${qs}`
        );
        // BE explicitly provides has_more; next_cursor also kept for loadMore()
        setNextCursor(res.data.has_more ? res.data.next_cursor : null);
        setEvents((prev) =>
          append ? [...prev, ...res.data.events] : res.data.events,
        );
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsLoading(false);
      }
    },
    [workItemId],
  );

  useEffect(() => {
    setCursor(null);
    setEvents([]);
    void fetchPage(null, false);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    if (!nextCursor) return;
    setCursor(nextCursor);
    void fetchPage(nextCursor, true);
  }, [nextCursor, fetchPage]);

  const refetch = useCallback(() => {
    setCursor(null);
    setEvents([]);
    void fetchPage(null, false);
  }, [fetchPage]);

  return {
    events,
    isLoading,
    error,
    hasMore: Boolean(nextCursor),
    loadMore,
    refetch,
  };
}
