'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useTimeline } from '@/hooks/work-item/use-timeline';
import { TimelineEventItem } from './timeline-event-item';

interface TimelineTabProps {
  workItemId: string;
}

export function TimelineTab({ workItemId }: TimelineTabProps) {
  const t = useTranslations('workspace.itemDetail.timeline');
  const { events, isLoading, error, hasMore, loadMore } = useTimeline(workItemId);

  if (isLoading && events.length === 0) {
    return (
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
    );
  }

  if (error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t('errorBanner')}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {events.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('empty')}</p>
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

      {hasMore && (
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
