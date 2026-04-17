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
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchPage = useCallback(
    async (pageNum: number, append: boolean) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await apiGet<TimelineResponse>(
          `/api/v1/work-items/${workItemId}/timeline?page=${pageNum}&page_size=${PAGE_SIZE}`
        );
        setTotal(res.total);
        setEvents((prev) => (append ? [...prev, ...res.data] : res.data));
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsLoading(false);
      }
    },
    [workItemId]
  );

  useEffect(() => {
    setPage(1);
    setEvents([]);
    void fetchPage(1, false);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    const nextPage = page + 1;
    setPage(nextPage);
    void fetchPage(nextPage, true);
  }, [page, fetchPage]);

  const refetch = useCallback(() => {
    setPage(1);
    setEvents([]);
    void fetchPage(1, false);
  }, [fetchPage]);

  const hasMore = events.length < total;

  return { events, isLoading, error, hasMore, loadMore, refetch };
}
