'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Bell, CheckCheck, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageContainer } from '@/components/layout/page-container';
import { NotificationItem } from '@/components/notifications/notification-item';
import { listNotifications, markRead as apiMarkRead, markAllRead as apiMarkAllRead } from '@/lib/api/notifications';
import { isSessionExpired } from '@/lib/types/auth';
import type { NotificationV2 } from '@/lib/types/api';

interface InboxPageProps {
  params: { slug: string };
}

export default function InboxPage({ params: { slug } }: InboxPageProps) {
  const t = useTranslations('workspace.inbox');
  const router = useRouter();

  const [notifications, setNotifications] = useState<NotificationV2[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isMarkingAll, setIsMarkingAll] = useState(false);

  const PAGE_SIZE = 20;

  const fetchNotifications = useCallback(
    async (pg = 1, unreadOnly = onlyUnread) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await listNotifications(pg, PAGE_SIZE, unreadOnly);
        setNotifications(res.data.items);
        setTotal(res.data.total);
        setPage(pg);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsLoading(false);
      }
    },
    [onlyUnread]
  );

  useEffect(() => {
    void fetchNotifications(1, onlyUnread);
  }, [fetchNotifications, onlyUnread]);

  const handleMarkRead = useCallback(
    async (id: string) => {
      // Optimistic update
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, state: 'read' as const } : n))
      );
      try {
        await apiMarkRead(id);
      } catch {
        // Revert
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, state: 'unread' as const } : n))
        );
      }
    },
    []
  );

  const handleMarkAllRead = useCallback(async () => {
    setIsMarkingAll(true);
    // Optimistic
    setNotifications((prev) =>
      prev.map((n) => (n.state === 'unread' ? { ...n, state: 'read' as const } : n))
    );
    try {
      await apiMarkAllRead();
    } catch {
      // Reload on failure
      void fetchNotifications(page);
    } finally {
      setIsMarkingAll(false);
    }
  }, [fetchNotifications, page]);

  async function handleClick(notification: NotificationV2) {
    if (notification.state === 'unread') {
      await handleMarkRead(notification.id);
    }
    if (notification.deeplink) {
      router.push(notification.deeplink);
    }
  }

  function handleToggleUnread() {
    const next = !onlyUnread;
    setOnlyUnread(next);
    // fetchNotifications will be called via useEffect when onlyUnread changes
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Loading skeleton
  if (isLoading) {
    return (
      <PageContainer variant="narrow">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-h2 font-semibold">{t('title')}</h1>
        </div>
        <div className="space-y-2" data-skeleton>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-3 rounded-md p-3">
              <Skeleton className="h-4 w-4 rounded-full" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
      </PageContainer>
    );
  }

  if (error) {
    if (isSessionExpired(error)) return null;
    return (
      <PageContainer variant="narrow">
        <h1 className="mb-6 text-h2 font-semibold">{t('title')}</h1>
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3">
          <p className="text-body-sm text-destructive">
            {t('errorBanner')}: {error.message}
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() => void fetchNotifications(page)}
          >
            <RefreshCw className="mr-1 h-3 w-3" />
            {t('retry')}
          </Button>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer variant="narrow">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-h2 font-semibold">{t('title')}</h1>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleToggleUnread}
            className="flex items-center gap-1.5"
          >
            <input
              type="checkbox"
              checked={onlyUnread}
              readOnly
              aria-label={t('onlyUnread')}
              className="pointer-events-none"
            />
            <span>{t('onlyUnread')}</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleMarkAllRead()}
            disabled={isMarkingAll}
            aria-label={t('markAllRead')}
          >
            <CheckCheck className="mr-1 h-3.5 w-3.5" />
            {t('markAllRead')}
          </Button>
        </div>
      </div>

      {notifications.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <Bell className="h-10 w-10 opacity-30" />
          <p className="text-body">{t('empty')}</p>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1">
            {notifications.map((n) => (
              <div
                key={n.id}
                className="cursor-pointer rounded-md"
                onClick={() => void handleClick(n)}
                data-unread={n.state === 'unread'}
              >
                <NotificationItem
                  notification={n}
                  onMarkRead={(id) => void handleMarkRead(id)}
                />
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => void fetchNotifications(page - 1)}
              >
                {t('prev')}
              </Button>
              <span className="text-body-sm text-muted-foreground">
                {t('pageOf', { page, total: totalPages })}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => void fetchNotifications(page + 1)}
              >
                {t('next')}
              </Button>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}
