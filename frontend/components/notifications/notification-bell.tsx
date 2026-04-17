'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { Bell } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Skeleton } from '@/components/ui/skeleton';
import { useUnreadCount } from '@/hooks/use-unread-count';
import { NotificationItem } from './notification-item';
import { NotificationSheet } from './notification-sheet';
import { listNotifications, markRead as apiMarkRead } from '@/lib/api/notifications';
import type { NotificationV2 } from '@/lib/types/api';

const DND_KEY = 'notifications.muted';

const MAX_PREVIEW = 10;

interface NotificationBellProps {
  slug: string;
}

export function NotificationBell({ slug }: NotificationBellProps) {
  const t = useTranslations('workspace.notificationBell');
  const { count, refetch: refetchCount } = useUnreadCount();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationV2[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sheetNotification, setSheetNotification] = useState<NotificationV2 | null>(null);

  async function loadNotifications() {
    setIsLoading(true);
    setLoadError(null);
    try {
      const res = await listNotifications(1, MAX_PREVIEW);
      setItems(res.data.items);
    } catch {
      setLoadError(t('loadError'));
    } finally {
      setIsLoading(false);
    }
  }

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next) {
      void loadNotifications();
    }
  }

  const handleMarkRead = useCallback(
    async (id: string) => {
      setItems((prev) =>
        prev.map((n) => (n.id === id ? { ...n, state: 'read' as const } : n))
      );
      try {
        await apiMarkRead(id);
        refetchCount();
      } catch {
        // Revert optimistic update
        setItems((prev) =>
          prev.map((n) => (n.id === id ? { ...n, state: 'unread' as const } : n))
        );
      }
    },
    [refetchCount]
  );

  const badgeText = count >= 100 ? '99+' : String(count);

  return (
    <>
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t('ariaLabel')}
          className="relative"
        >
          <Bell className="h-5 w-5" />
          {count > 0 && (
            <span
              data-badge
              className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-0.5 text-[10px] font-bold text-destructive-foreground"
            >
              {badgeText}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        role="dialog"
        aria-label={t('popoverLabel')}
        className="w-80 p-0"
        align="end"
      >
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-body-sm font-semibold">{t('title')}</span>
          <Link
            href={`/workspace/${slug}/inbox`}
            className="text-body-sm text-primary hover:underline"
          >
            {t('viewAll')}
          </Link>
        </div>

        <div className="max-h-80 overflow-y-auto py-1">
          {isLoading ? (
            <div className="space-y-2 px-3 py-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center gap-3">
                  <Skeleton className="h-4 w-4 rounded-full" />
                  <div className="flex-1 space-y-1">
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-2/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : loadError ? (
            <p className="px-4 py-6 text-center text-body-sm text-destructive">{loadError}</p>
          ) : items.length === 0 ? (
            <p className="px-4 py-6 text-center text-body-sm text-muted-foreground">
              {t('empty')}
            </p>
          ) : (
            items.map((n) => (
              <NotificationItem
                key={n.id}
                notification={n}
                onMarkRead={(id) => void handleMarkRead(id)}
                onOpenSheet={(notif) => {
                  setOpen(false);
                  setSheetNotification(notif);
                }}
              />
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>

    <NotificationSheet
      notification={sheetNotification}
      open={sheetNotification !== null}
      onClose={() => setSheetNotification(null)}
      onMarkActioned={(id) => {
        setItems((prev) =>
          prev.map((n) => (n.id === id ? { ...n, state: 'actioned' as const } : n)),
        );
        setSheetNotification(null);
        refetchCount();
      }}
    />
  </>
  );
}
