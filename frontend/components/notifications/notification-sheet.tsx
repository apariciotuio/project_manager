'use client';

import { useTranslations } from 'next-intl';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/domain/relative-time';
import { markActioned as apiMarkActioned } from '@/lib/api/notifications';
import { useState } from 'react';
import type { NotificationV2 } from '@/lib/types/api';

export interface NotificationSheetProps {
  notification: NotificationV2 | null;
  open: boolean;
  onClose: () => void;
  onMarkActioned: (id: string) => void;
}

export function NotificationSheet({
  notification,
  open,
  onClose,
  onMarkActioned,
}: NotificationSheetProps) {
  const t = useTranslations('workspace.inbox');
  const [isPending, setIsPending] = useState(false);

  if (!notification) return null;

  const summary = String(notification.extra['summary'] ?? notification.type);
  const actor = typeof notification.extra['actor_name'] === 'string'
    ? notification.extra['actor_name']
    : null;

  const isActionRequired = notification.quick_action !== null;
  const isActioned = notification.state === 'actioned';

  async function handleMarkActioned() {
    setIsPending(true);
    try {
      await apiMarkActioned(notification!.id);
      onMarkActioned(notification!.id);
    } finally {
      setIsPending(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle data-testid="sheet-title">{summary}</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {actor && (
            <div>
              <span className="text-xs font-medium text-muted-foreground uppercase">
                {t('sheet.actor')}
              </span>
              <p className="text-sm mt-0.5" data-testid="sheet-actor">{actor}</p>
            </div>
          )}

          <div>
            <span className="text-xs font-medium text-muted-foreground uppercase">
              {t('sheet.received')}
            </span>
            <div className="mt-0.5">
              <RelativeTime iso={notification.created_at} />
            </div>
          </div>
        </div>

        {isActionRequired && !isActioned && (
          <SheetFooter>
            <Button
              data-testid="mark-actioned-btn"
              onClick={() => void handleMarkActioned()}
              disabled={isPending}
            >
              {t('sheet.markActioned')}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}
