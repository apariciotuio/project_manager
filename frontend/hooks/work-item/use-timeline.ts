'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { apiGet } from '@/lib/api-client';
import type { TimelineEvent, TimelineResponse } from '@/lib/types/work-item-detail';
import type { TimelineEventType, ActorType } from '@/lib/types/versions';

const PAGE_SIZE = 20;

export interface TimelineFiltersValue {
  eventTypes: TimelineEventType[];
  actorTypes: ActorType[];
  dateRange: { from: string | null; to: string | null };
}

interface UseTimelineResult {
  events: TimelineEvent[];
  isLoading: boolean;
  error: Error | null;
  hasMore: boolean;
  loadMore: () => void;
  refetch: () => void;
}

function buildQuery(cursor: string | null, filters?: TimelineFiltersValue): string {
  const params = new URLSearchParams();
  params.set('limit', String(PAGE_SIZE));
  if (cursor) params.set('cursor', cursor);
  if (filters) {
    for (const t of filters.eventTypes) params.append('event_types', t);
    for (const t of filters.actorTypes) params.append('actor_types', t);
    if (filters.dateRange.from) params.set('from_date', filters.dateRange.from);
    if (filters.dateRange.to) params.set('to_date', filters.dateRange.to);
  }
  return `?${params.toString()}`;
}

export function useTimeline(
  workItemId: string,
  filters?: TimelineFiltersValue,
): UseTimelineResult {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  // Stable identity for filter object — callers may recreate it on every render
  const filterKey = useMemo(
    () =>
      filters
        ? JSON.stringify({
            e: filters.eventTypes,
            a: filters.actorTypes,
            d: filters.dateRange,
          })
        : '',
    [filters],
  );

  const fetchPage = useCallback(
    async (cursorValue: string | null, append: boolean) => {
      setIsLoading(true);
      setError(null);
      try {
        const qs = buildQuery(cursorValue, filters);
        const res = await apiGet<TimelineResponse>(
          `/api/v1/work-items/${workItemId}/timeline${qs}`,
        );
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
    // filterKey captures filter content; stable across re-renders with equal contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [workItemId, filterKey],
  );

  useEffect(() => {
    setEvents([]);
    setNextCursor(null);
    void fetchPage(null, false);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    if (!nextCursor) return;
    void fetchPage(nextCursor, true);
  }, [nextCursor, fetchPage]);

  const refetch = useCallback(() => {
    setEvents([]);
    setNextCursor(null);
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
