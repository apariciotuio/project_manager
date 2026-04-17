'use client';

import { RelativeTime } from '@/components/domain/relative-time';
import type { TimelineEvent, TimelineEventType } from '@/lib/types/work-item-detail';
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
  Bot,
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

export interface TimelineEventItemProps {
  event: TimelineEvent;
}

export function TimelineEventItem({ event }: TimelineEventItemProps) {
  const isAi = event.actor_type === 'ai_suggestion';
  const Icon = isAi ? Bot : (EVENT_ICONS[event.event_type] ?? FileEdit);

  return (
    <li className="relative flex gap-3 pb-5 last:pb-0">
      <div
        className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background border border-border"
        aria-hidden
        data-event-type={event.event_type}
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
}
