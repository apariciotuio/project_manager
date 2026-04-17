'use client';

import {
  AtSign,
  UserCheck,
  RefreshCcw,
  MessageSquare,
  ClipboardCheck,
  Bell,
  CheckCircle2,
} from 'lucide-react';
import { RelativeTime } from '@/components/domain/relative-time';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { NotificationV2, QuickAction } from '@/lib/types/api';

const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  mention: AtSign,
  assignment: UserCheck,
  state_change: RefreshCcw,
  comment: MessageSquare,
  review_request: ClipboardCheck,
};

function getIcon(type: string): React.ComponentType<{ className?: string }> {
  return TYPE_ICONS[type] ?? Bell;
}

function getSummary(notification: NotificationV2): string {
  const extra = notification.extra;
  if (typeof extra['summary'] === 'string') return extra['summary'];
  if (typeof extra['title'] === 'string') return extra['title'];
  return notification.type;
}

function getActor(notification: NotificationV2): string | null {
  const extra = notification.extra;
  if (typeof extra['actor_name'] === 'string') return extra['actor_name'];
  return null;
}

export interface NotificationItemProps {
  notification: NotificationV2;
  onMarkRead: (id: string) => void;
  onExecuteAction?: (id: string, action: QuickAction) => void;
  onOpenSheet?: (notification: NotificationV2) => void;
  isLoading?: boolean;
}

export function NotificationItem({
  notification,
  onMarkRead,
  onExecuteAction,
  onOpenSheet,
  isLoading = false,
}: NotificationItemProps) {
  const Icon = getIcon(notification.type);
  const summary = getSummary(notification);
  const actor = getActor(notification);
  const isUnread = notification.state === 'unread';
  const isActioned = notification.state === 'actioned';

  function handleMouseEnter() {
    if (isUnread) {
      onMarkRead(notification.id);
    }
  }

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md px-3 py-2 transition-colors hover:bg-accent',
        isUnread && 'bg-primary/5'
      )}
      onMouseEnter={handleMouseEnter}
      data-notification-id={notification.id}
      data-state={notification.state}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className={cn('text-body-sm text-foreground', isUnread && 'font-semibold')}>
          {summary}
        </p>
        {actor && (
          <p className="text-body-sm text-muted-foreground">{actor}</p>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <RelativeTime iso={notification.created_at} />
        <div className="flex items-center gap-1">
          {isActioned && (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" aria-label="Actioned" />
          )}
          {isUnread && (
            <span className="h-2 w-2 rounded-full bg-primary" aria-label="Unread" />
          )}
        </div>
        {notification.quick_action && !isActioned && onExecuteAction && (
          <Button
            size="sm"
            variant="outline"
            className="h-6 px-2 text-xs"
            disabled={isLoading}
            onClick={(e) => {
              e.stopPropagation();
              if (notification.quick_action) {
                onExecuteAction(notification.id, notification.quick_action);
              }
            }}
          >
            {isLoading ? '…' : notification.quick_action.action}
          </Button>
        )}
      </div>
    </div>
  );
}
