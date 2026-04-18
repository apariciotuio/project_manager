'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Bell, CheckCheck, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageContainer } from '@/components/layout/page-container';
import { NotificationItem } from '@/components/notifications/notification-item';
import { InboxFilterBarWithUrlSync } from '@/components/notifications/inbox-filter-bar';
import { NotificationSheet } from '@/components/notifications/notification-sheet';
import {
  listNotifications,
  markRead as apiMarkRead,
  markAllRead as apiMarkAllRead,
} from '@/lib/api/notifications';
import { isSessionExpired } from '@/lib/types/auth';
import type { NotificationV2 } from '@/lib/types/api';
import type { InboxFilter } from '@/components/notifications/inbox-filter-bar';

interface InboxPageProps {
  params: { slug: string };
}

// Map filter tab to API params
function filterToApiParams(filter: InboxFilter): {
  onlyUnread: boolean;
  typeFilter: string | null;
} {
  switch (filter) {
    case 'unread':
      return { onlyUnread: true, typeFilter: null };
    case 'mentions':
      return { onlyUnread: false, typeFilter: 'mention' };
    case 'reviews':
      return { onlyUnread: false, typeFilter: 'review_request' };
    default:
      return { onlyUnread: false, typeFilter: null };
  }
}

export default function InboxPage({ params: { slug } }: InboxPageProps) {
  const t = useTranslations('workspace.inbox');
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeFilter = (searchParams.get('filter') ?? 'all') as InboxFilter;
  const searchTerm = (searchParams.get('search') ?? '').toLowerCase();

  const [notifications, setNotifications] = useState<NotificationV2[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [sheetNotification, setSheetNotification] = useState<NotificationV2 | null>(null);

  const PAGE_SIZE = 20;

  const { onlyUnread } = filterToApiParams(activeFilter);

  const fetchNotifications = useCallback(
    async (pg = 1, append = false) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await listNotifications(pg, PAGE_SIZE, onlyUnread);
        setNotifications((prev) =>
          append ? [...prev, ...res.data.items] : res.data.items,
        );
        setTotal(res.data.total);
        setPage(pg);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsLoading(false);
      }
    },
    [onlyUnread],
  );

  const handleLoadMore = useCallback(async () => {
    await fetchNotifications(page + 1, true);
  }, [fetchNotifications, page]);

  useEffect(() => {
    void fetchNotifications(1);
  }, [fetchNotifications]);

  // Client-side search + type filter
  const visibleNotifications = useMemo(() => {
    const { typeFilter } = filterToApiParams(activeFilter);
    return notifications.filter((n) => {
      // Type filter (mentions/reviews)
      if (typeFilter && n.type !== typeFilter) return false;
      // Search filter: match summary or actor
      if (searchTerm) {
        const summary = String(n.extra['summary'] ?? n.type).toLowerCase();
        const actor = String(n.extra['actor_name'] ?? '').toLowerCase();
        if (!summary.includes(searchTerm) && !actor.includes(searchTerm)) return false;
      }
      return true;
    });
  }, [notifications, activeFilter, searchTerm]);

  const handleMarkRead = useCallback(async (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, state: 'read' as const } : n)),
    );
    try {
      await apiMarkRead(id);
    } catch {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, state: 'unread' as const } : n)),
      );
    }
  }, []);

  const handleMarkAllRead = useCallback(async () => {
    setIsMarkingAll(true);
    setNotifications((prev) =>
      prev.map((n) => (n.state === 'unread' ? { ...n, state: 'read' as const } : n)),
    );
    try {
      await apiMarkAllRead();
    } catch {
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
    } else {
      // No deeplink — open the sheet
      setSheetNotification(notification);
    }
  }

  function handleOpenSheet(notification: NotificationV2) {
    setSheetNotification(notification);
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

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
        <div
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3"
        >
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
            onClick={() => void handleMarkAllRead()}
            disabled={isMarkingAll}
            aria-label={t('markAllRead')}
          >
            <CheckCheck className="mr-1 h-3.5 w-3.5" />
            {t('markAllRead')}
          </Button>
        </div>
      </div>

      <div className="mb-4">
        <InboxFilterBarWithUrlSync />
      </div>

      {visibleNotifications.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <Bell className="h-10 w-10 opacity-30" />
          <p className="text-body">{t('empty')}</p>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1" data-testid="inbox-list">
            {visibleNotifications.map((n) => (
              <div
                key={n.id}
                className="cursor-pointer rounded-md"
                onClick={() => void handleClick(n)}
                data-unread={n.state === 'unread'}
              >
                <NotificationItem
                  notification={n}
                  onMarkRead={(id) => void handleMarkRead(id)}
                  onOpenSheet={handleOpenSheet}
                />
              </div>
            ))}
          </div>

          {page < totalPages && (
            <div className="mt-4 flex items-center justify-center">
              <Button
                variant="outline"
                size="sm"
                disabled={isLoading}
                onClick={() => void handleLoadMore()}
              >
                {t('loadMore')}
              </Button>
            </div>
          )}
        </>
      )}

      <NotificationSheet
        notification={sheetNotification}
        open={sheetNotification !== null}
        onClose={() => setSheetNotification(null)}
        onMarkActioned={(id) => {
          setNotifications((prev) =>
            prev.map((n) =>
              n.id === id ? { ...n, state: 'actioned' as const } : n,
            ),
          );
          setSheetNotification(null);
        }}
      />
    </PageContainer>
  );
}
