'use client';

/**
 * EP-08 — SSE notifications hook.
 *
 * Flow: fetch stream-token → build url → delegate EventSource lifecycle to useSSE.
 * Token refresh is retried before each reconnect (useSSE.onBeforeReconnect).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSSE } from '@/hooks/use-sse';
import { getStreamToken } from '@/lib/api/notifications-api';

export interface NotificationEvent {
  type: 'notification.created' | 'notification.updated' | 'notification.deleted';
  data: Record<string, unknown>;
}

const SSE_EVENTS: string[] = [
  'notification.created',
  'notification.updated',
  'notification.deleted',
];

const STREAM_BASE =
  (process.env['NEXT_PUBLIC_API_BASE_URL'] ?? '') + '/api/v1/notifications/stream';

function buildStreamUrl(token: string): string {
  return `${STREAM_BASE}?token=${encodeURIComponent(token)}`;
}

/**
 * Fetches a stream-token then opens a persistent SSE connection via useSSE.
 *
 * @param onEvent   - Called for each notification.created/updated/deleted event
 * @param enabled   - Set false to suppress connection (e.g. DND, unauthenticated)
 */
export function useSSENotifications(
  onEvent: (ev: NotificationEvent) => void,
  enabled = true,
): void {
  const [url, setUrl] = useState<string>('');
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const refreshUrl = useCallback(async () => {
    try {
      const token = await getStreamToken();
      setUrl(buildStreamUrl(token));
    } catch (err) {
      console.error('[useSSENotifications] failed to fetch stream token', err);
      setUrl('');
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setUrl('');
      return;
    }
    void refreshUrl();
  }, [enabled, refreshUrl]);

  const handleMessage = useCallback((event: MessageEvent) => {
    const type = event.type as NotificationEvent['type'];
    try {
      const data = JSON.parse(event.data as string) as Record<string, unknown>;
      onEventRef.current({ type, data });
    } catch {
      // malformed JSON — skip
    }
  }, []);

  useSSE(url, handleMessage, {
    enabled: enabled && url !== '',
    extraEvents: SSE_EVENTS,
    onBeforeReconnect: refreshUrl,
  });
}
