'use client';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { RelativeTime } from '@/components/domain/relative-time';
import { useTimeline } from '@/hooks/work-item/use-timeline';
import type { TimelineEventType } from '@/lib/types/work-item-detail';
import {
  ArrowRightLeft,
  FileEdit,
  CheckSquare,
  CheckCircle2,
  Eye,
  CheckCheck,
  MessageCircle,
  UserCog,
  Tag,
} from 'lucide-react';

const EVENT_ICONS: Record<TimelineEventType, React.ComponentType<{ className?: string }>> = {
  state_transition: ArrowRightLeft,
  owner_changed: UserCog,
  section_updated: FileEdit,
  task_added: CheckSquare,
  task_completed: CheckCircle2,
  review_requested: Eye,
  review_completed: CheckCheck,
  comment_added: MessageCircle,
  tag_added: Tag,
  tag_removed: Tag,
};

interface TimelineTabProps {
  workItemId: string;
}

export function TimelineTab({ workItemId }: TimelineTabProps) {
  const { events, isLoading, hasMore, loadMore } = useTimeline(workItemId);

  return (
    <div className="flex flex-col gap-4">
      {isLoading && events.length === 0 ? (
        Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-3 items-start">
            <Skeleton className="h-8 w-8 rounded-full shrink-0" />
            <div className="flex-1 flex flex-col gap-1.5 pt-1">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        ))
      ) : (
        <>
          <ol
            aria-label="Historial de actividad"
            className="relative flex flex-col gap-0 before:absolute before:left-[15px] before:top-4 before:bottom-4 before:w-px before:bg-border"
          >
            {events.map((event) => {
              const Icon = EVENT_ICONS[event.event_type] ?? FileEdit;
              return (
                <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                  <div
                    className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background border border-border"
                    aria-hidden
                  >
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <div className="flex flex-col gap-0.5 pt-1 min-w-0">
                    <p className="text-sm text-foreground">
                      {event.actor_display_name && (
                        <span className="font-medium">{event.actor_display_name} </span>
                      )}
                      {event.summary}
                    </p>
                    <RelativeTime iso={event.occurred_at} />
                  </div>
                </li>
              );
            })}
          </ol>

          {hasMore && (
            <Button
              variant="outline"
              size="sm"
              onClick={loadMore}
              disabled={isLoading}
              className="self-center"
            >
              {isLoading ? 'Cargando…' : 'Cargar más'}
            </Button>
          )}

          {events.length === 0 && !isLoading && (
            <p className="text-sm text-muted-foreground">Sin actividad todavía.</p>
          )}
        </>
      )}
    </div>
  );
}
