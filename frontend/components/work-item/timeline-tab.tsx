'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useTimeline, type TimelineFiltersValue } from '@/hooks/work-item/use-timeline';
import { TimelineFilters } from '@/components/timeline/TimelineFilters';
import { TimelineEventItem } from './timeline-event-item';

interface TimelineTabProps {
  workItemId: string;
}

const EMPTY_FILTERS: TimelineFiltersValue = {
  eventTypes: [],
  actorTypes: [],
  dateRange: { from: null, to: null },
};

function isFiltered(f: TimelineFiltersValue): boolean {
  return (
    f.eventTypes.length > 0 ||
    f.actorTypes.length > 0 ||
    f.dateRange.from !== null ||
    f.dateRange.to !== null
  );
}

export function TimelineTab({ workItemId }: TimelineTabProps) {
  const t = useTranslations('workspace.itemDetail.timeline');
  const [filters, setFilters] = useState<TimelineFiltersValue>(EMPTY_FILTERS);
  const { events, isLoading, error, hasMore, loadMore } = useTimeline(
    workItemId,
    filters,
  );

  const filtered = isFiltered(filters);

  return (
    <div className="flex flex-col gap-4">
      <TimelineFilters {...filters} onChange={setFilters} />

      {isLoading && events.length === 0 ? (
        <div className="flex flex-col gap-4" aria-busy="true" aria-label={t('loading')}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-3 items-start">
              <Skeleton className="h-8 w-8 rounded-full shrink-0" />
              <div className="flex-1 flex flex-col gap-1.5 pt-1">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <p role="alert" className="text-sm text-destructive">
          {t('errorBanner')}
        </p>
      ) : events.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t(filtered ? 'emptyFiltered' : 'empty')}
        </p>
      ) : (
        <ol
          aria-label={t('listAria')}
          className="relative flex flex-col gap-0 before:absolute before:left-[15px] before:top-4 before:bottom-4 before:w-px before:bg-border"
        >
          {events.map((event) => (
            <TimelineEventItem key={event.id} event={event} />
          ))}
        </ol>
      )}

      {!isLoading && !error && hasMore && (
        <Button
          variant="outline"
          size="sm"
          onClick={loadMore}
          disabled={isLoading}
          className="self-center"
        >
          {isLoading ? t('loading') : t('loadMore')}
        </Button>
      )}
    </div>
  );
}
