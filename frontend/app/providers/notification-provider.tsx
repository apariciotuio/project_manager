'use client';

/**
 * EP-08 — NotificationProvider.
 *
 * Single global SSE connection per session (mount once in workspace layout).
 * Merges real-time SSE events into local state without extra network round-trips.
 * Invalidates unreadCount on notification.created / notification.updated.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import {
  listNotifications,
  getUnreadCount,
  markRead as apiMarkRead,
  markActioned as apiMarkActioned,
  executeAction as apiExecuteAction,
} from '@/lib/api/notifications-api';
import { useSSENotifications } from '@/hooks/use-sse-notifications';
import type { NotificationEvent } from '@/hooks/use-sse-notifications';
import type { NotificationV2 } from '@/lib/types/api';

// Coalesce unread-count server reconciliations within this window.
// SSE bursts should not trigger one GET per event.
const UNREAD_COUNT_DEBOUNCE_MS = 250;

// ─── Context shape ────────────────────────────────────────────────────────────

interface NotificationContextValue {
  notifications: NotificationV2[];
  unreadCount: number;
  isLoading: boolean;
  markRead: (id: string) => Promise<void>;
  markActioned: (id: string) => Promise<void>;
  executeAction: (id: string, params?: Record<string, unknown>) => Promise<void>;
  refetch: () => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationV2[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchTick, setFetchTick] = useState(0);

  // Coalesce rapid reconcile calls + order-stamp responses so out-of-order
  // GETs cannot clobber newer values.
  const reconcileTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconcileSeqRef = useRef(0);

  const reconcileUnreadCount = useCallback(() => {
    if (reconcileTimerRef.current) return;
    reconcileTimerRef.current = setTimeout(() => {
      reconcileTimerRef.current = null;
      const seq = ++reconcileSeqRef.current;
      void getUnreadCount()
        .then((count) => {
          // Drop stale responses — only apply if no newer call was fired
          if (seq === reconcileSeqRef.current) setUnreadCount(count);
        })
        .catch(() => {
          /* ignore */
        });
    }, UNREAD_COUNT_DEBOUNCE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (reconcileTimerRef.current) clearTimeout(reconcileTimerRef.current);
    };
  }, []);

  // Fetch notifications + unread count
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const seq = ++reconcileSeqRef.current;
        const [list, count] = await Promise.all([listNotifications(), getUnreadCount()]);
        if (!cancelled) {
          setNotifications(list.data.items);
          if (seq === reconcileSeqRef.current) setUnreadCount(count);
        }
      } catch {
        // Errors are non-fatal here; consumers handle their own error states
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [fetchTick]);

  const refetch = useCallback(() => {
    setFetchTick((t) => t + 1);
  }, []);

  // SSE event handler — merge into local state and debounce server reconcile
  const handleSSEEvent = useCallback((ev: NotificationEvent) => {
    if (ev.type === 'notification.created') {
      const notif = ev.data as unknown as NotificationV2;
      setNotifications((prev) => [notif, ...prev]);
      setUnreadCount((c) => c + 1);
      reconcileUnreadCount();
    } else if (ev.type === 'notification.updated') {
      const updated = ev.data as unknown as NotificationV2;
      setNotifications((prev) =>
        prev.map((n) => (n.id === updated.id ? updated : n))
      );
      reconcileUnreadCount();
    } else if (ev.type === 'notification.deleted') {
      const { id } = ev.data as { id: string };
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      reconcileUnreadCount();
    }
  }, [reconcileUnreadCount]);

  useSSENotifications(handleSSEEvent);

  const markRead = useCallback(async (id: string) => {
    // Optimistic update
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, state: 'read' as const, read_at: new Date().toISOString() } : n))
    );
    setUnreadCount((c) => Math.max(0, c - 1));
    try {
      await apiMarkRead(id);
    } catch {
      // Revert optimistic update on error
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, state: 'unread' as const, read_at: null } : n))
      );
      setUnreadCount((c) => c + 1);
    }
  }, []);

  const markActioned = useCallback(async (id: string) => {
    setNotifications((prev) =>
      prev.map((n) =>
        n.id === id ? { ...n, state: 'actioned' as const, actioned_at: new Date().toISOString() } : n
      )
    );
    await apiMarkActioned(id);
  }, []);

  const executeAction = useCallback(
    async (id: string, params?: Record<string, unknown>) => {
      await apiExecuteAction(id, params);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === id
            ? { ...n, state: 'actioned' as const, actioned_at: new Date().toISOString() }
            : n
        )
      );
    },
    []
  );

  return (
    <NotificationContext.Provider
      value={{ notifications, unreadCount, isLoading, markRead, markActioned, executeAction, refetch }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useNotificationContext(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error('useNotificationContext must be used within NotificationProvider');
  }
  return ctx;
}
