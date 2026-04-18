'use client';

import { useState } from 'react';
import { TimelineTab } from '@/components/work-item/timeline-tab';
import { TimelineFilters } from '@/components/timeline/TimelineFilters';
import { TimelineEventItem } from '@/components/work-item/timeline-event-item';
import { useTimeline } from '@/hooks/work-item/use-timeline';
import type { TimelineFilterState } from '@/components/timeline/TimelineFilters';

interface TimelinePageProps {
  params: { slug: string; id: string };
}

const EMPTY_FILTERS: TimelineFilterState = {
  eventTypes: [],
  actorTypes: [],
  dateRange: { from: null, to: null },
};

export default function TimelinePage({ params: { id } }: TimelinePageProps) {
  const [filters, setFilters] = useState<TimelineFilterState>(EMPTY_FILTERS);

  function handleFiltersChange(next: TimelineFilterState) {
    setFilters(next);
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h2 className="text-lg font-semibold">Activity</h2>
      <TimelineFilters
        eventTypes={filters.eventTypes}
        actorTypes={filters.actorTypes}
        dateRange={filters.dateRange}
        onChange={handleFiltersChange}
      />
      <TimelineTabWithFilters workItemId={id} filters={filters} />
    </div>
  );
}

/**
 * Thin wrapper that passes active filters down to TimelineTab.
 * TimelineTab currently fetches without filters — this component
 * adds client-side filtering until the BE query params are wired.
 * TODO: pass filter params to useTimeline once BE supports them (EP-07 backend).
 */
function TimelineTabWithFilters({
  workItemId,
  filters,
}: {
  workItemId: string;
  filters: TimelineFilterState;
}) {
  // If no active filters, delegate fully to TimelineTab (zero overhead)
  const hasFilters =
    filters.eventTypes.length > 0 ||
    filters.actorTypes.length > 0 ||
    filters.dateRange.from !== null ||
    filters.dateRange.to !== null;

  if (!hasFilters) {
    return <TimelineTab workItemId={workItemId} />;
  }

  return <FilteredTimelineFeed workItemId={workItemId} filters={filters} />;
}

/**
 * Renders a filtered view of the timeline.
 * Client-side filtering only — resets cursor on filter change.
 */
function FilteredTimelineFeed({
  workItemId,
  filters,
}: {
  workItemId: string;
  filters: TimelineFilterState;
}) {
  const { events, isLoading, error, hasMore, loadMore } = useTimeline(workItemId);

  const filtered = events.filter((evt) => {
    if (
      filters.eventTypes.length > 0 &&
      !filters.eventTypes.includes(evt.event_type)
    ) {
      return false;
    }
    if (
      filters.actorTypes.length > 0 &&
      !filters.actorTypes.includes(evt.actor_type)
    ) {
      return false;
    }
    if (filters.dateRange.from !== null) {
      if (evt.occurred_at < filters.dateRange.from) return false;
    }
    if (filters.dateRange.to !== null) {
      if (evt.occurred_at > filters.dateRange.to + 'T23:59:59Z') return false;
    }
    return true;
  });

  if (isLoading && events.length === 0) {
    return (
      <div aria-busy="true" className="text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Could not load activity.
      </p>
    );
  }

  if (filtered.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {events.length === 0 ? 'No activity yet.' : 'No events match these filters.'}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ol
        aria-label="Activity"
        className="relative flex flex-col gap-0 before:absolute before:left-[15px] before:top-4 before:bottom-4 before:w-px before:bg-border"
      >
        {filtered.map((event) => (
          <TimelineEventItem key={event.id} event={event} />
        ))}
      </ol>
      {hasMore && (
        <button
          className="self-center text-sm text-muted-foreground underline"
          onClick={loadMore}
          disabled={isLoading}
        >
          Load more
        </button>
      )}
    </div>
  );
}
