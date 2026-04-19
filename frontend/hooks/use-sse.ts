'use client';

import { useEffect, useRef, useState } from 'react';

export type SSEStatus = 'connecting' | 'open' | 'closed' | 'error';

export interface SSEOptions {
  /** Max retry attempts before status transitions to 'error'. Default: Infinity */
  maxRetries?: number;
  /** Base delay in ms for exponential backoff. Default: 1000 */
  baseDelay?: number;
  /** Max delay cap in ms. Default: 30000 */
  maxDelay?: number;
  /** Called before each reconnect attempt — use for token refresh. */
  onBeforeReconnect?: () => void | Promise<void>;
  /**
   * Additional named SSE event types to subscribe to (e.g. ['done', 'error']).
   * Each event is dispatched to the same onMessage callback with event.type set.
   */
  extraEvents?: string[];
  /**
   * When false, the hook does not open an EventSource. Flip to true to connect.
   * Also skipped when url is an empty string. Default: true.
   */
  enabled?: boolean;
}

/**
 * Shared SSE hook — single place where EventSource + backoff lives.
 * All SSE consumers (EP-03 streaming, EP-08 notifications, EP-12 job progress)
 * must delegate to this hook. No direct `new EventSource(...)` outside here.
 */
export function useSSE(
  url: string,
  onMessage: (event: MessageEvent) => void,
  options: SSEOptions = {},
): { status: SSEStatus; close: () => void } {
  const {
    maxRetries = Infinity,
    baseDelay = 1000,
    maxDelay = 30000,
    onBeforeReconnect,
    extraEvents = [],
    enabled = true,
  } = options;

  const [status, setStatus] = useState<SSEStatus>('connecting');
  const retryCount = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const unmountedRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled || !url) {
      setStatus('closed');
      return;
    }
    unmountedRef.current = false;
    retryCount.current = 0;

    function connect() {
      if (unmountedRef.current) return;

      const es = new EventSource(url);
      esRef.current = es;
      setStatus('open');

      const messageHandler = (e: MessageEvent) => {
        if (!unmountedRef.current) onMessageRef.current(e);
      };
      es.addEventListener('message', messageHandler);

      // Subscribe to any additional named event types (e.g. 'done', 'error')
      const extraHandlers: Array<{ type: string; handler: (e: MessageEvent) => void }> = [];
      for (const eventType of extraEvents) {
        const handler = (e: MessageEvent) => {
          if (!unmountedRef.current) onMessageRef.current(e);
        };
        es.addEventListener(eventType, handler);
        extraHandlers.push({ type: eventType, handler });
      }

      es.onerror = () => {
        if (unmountedRef.current) return;
        es.removeEventListener('message', messageHandler);
        for (const { type, handler } of extraHandlers) {
          es.removeEventListener(type, handler);
        }
        es.close();

        if (retryCount.current >= maxRetries) {
          setStatus('error');
          return;
        }

        const delay = Math.min(baseDelay * 2 ** retryCount.current, maxDelay);
        retryCount.current += 1;

        timeoutRef.current = setTimeout(async () => {
          if (unmountedRef.current) return;
          await onBeforeReconnect?.();
          connect();
        }, delay);
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setStatus('closed');
    };
    // Re-connect on url / enabled change — onMessage is stable via ref
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, enabled]);

  function close() {
    unmountedRef.current = true;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setStatus('closed');
  }

  return { status, close };
}
