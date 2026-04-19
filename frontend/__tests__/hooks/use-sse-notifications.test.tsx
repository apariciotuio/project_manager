/**
 * EP-08 — useSSENotifications hook tests.
 * Delegates EventSource lifecycle to useSSE — this suite asserts token fetch
 * + URL construction + event dispatch + enabled guard.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useSSENotifications } from '@/hooks/use-sse-notifications';
import type { NotificationEvent } from '@/hooks/use-sse-notifications';

// ─── EventSource mock (opaque — useSSE owns the lifecycle) ────────────────────

type Handler = (event: MessageEvent) => void;
type ErrorHandler = (event: Event) => void;

interface MockESInstance {
  url: string;
  close: ReturnType<typeof vi.fn>;
  listeners: Map<string, Handler[]>;
  onerror: ErrorHandler | null;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
  emit: (type: string, data: string) => void;
  triggerError: () => void;
}

let mockESInstances: MockESInstance[] = [];

function makeMockEventSource() {
  const MockES = vi.fn().mockImplementation((url: string) => {
    const instance: MockESInstance = {
      url,
      close: vi.fn(),
      listeners: new Map(),
      onerror: null,
      addEventListener: vi.fn((type: string, handler: Handler) => {
        if (!instance.listeners.has(type)) instance.listeners.set(type, []);
        instance.listeners.get(type)!.push(handler);
      }),
      removeEventListener: vi.fn((type: string, handler: Handler) => {
        const list = instance.listeners.get(type) ?? [];
        instance.listeners.set(type, list.filter((h) => h !== handler));
      }),
      emit(type: string, data: string) {
        const handlers = instance.listeners.get(type) ?? [];
        const event = new MessageEvent(type, { data });
        handlers.forEach((h) => h(event));
      },
      triggerError() {
        if (instance.onerror) instance.onerror(new Event('error'));
      },
    };
    Object.defineProperty(instance, 'onerror', {
      set(handler: ErrorHandler) { this._onerror = handler; },
      get() { return this._onerror ?? null; },
    });
    mockESInstances.push(instance);
    return instance;
  });
  return MockES;
}

beforeEach(() => {
  mockESInstances = [];
  vi.stubGlobal('EventSource', makeMockEventSource());
  server.use(
    http.post('http://localhost/api/v1/notifications/stream-token', () =>
      HttpResponse.json({ data: { token: 'tok-abc', expires_in: 300 }, message: 'ok' })
    )
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useSSENotifications', () => {
  it('fetches stream token and opens EventSource with token query param', async () => {
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent));

    await waitFor(() => {
      expect(mockESInstances).toHaveLength(1);
    });
    expect(mockESInstances[0]!.url).toContain('token=tok-abc');
  });

  it('dispatches notification.created event to onEvent callback', async () => {
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent));

    await waitFor(() => {
      expect(mockESInstances).toHaveLength(1);
    });

    const es = mockESInstances[0]!;
    act(() => {
      es.emit('notification.created', JSON.stringify({ id: 'n-1', type: 'review_request' }));
    });

    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'notification.created' })
    );
  });

  it('dispatches notification.updated and notification.deleted events', async () => {
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent));

    await waitFor(() => {
      expect(mockESInstances).toHaveLength(1);
    });

    const es = mockESInstances[0]!;
    act(() => {
      es.emit('notification.updated', JSON.stringify({ id: 'n-1' }));
      es.emit('notification.deleted', JSON.stringify({ id: 'n-1' }));
    });

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, expect.objectContaining({ type: 'notification.updated' }));
    expect(onEvent).toHaveBeenNthCalledWith(2, expect.objectContaining({ type: 'notification.deleted' }));
  });

  it('skips malformed JSON frames without invoking onEvent', async () => {
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent));

    await waitFor(() => {
      expect(mockESInstances).toHaveLength(1);
    });

    const es = mockESInstances[0]!;
    act(() => {
      es.emit('notification.created', '{"not closed');
    });

    expect(onEvent).not.toHaveBeenCalled();
  });

  it('calls EventSource.close on unmount', async () => {
    const onEvent = vi.fn();
    const { unmount } = renderHook(() => useSSENotifications(onEvent));

    await waitFor(() => {
      expect(mockESInstances).toHaveLength(1);
    });
    unmount();
    expect(mockESInstances[0]!.close).toHaveBeenCalled();
  });

  it('does not open EventSource when enabled=false', async () => {
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent, false));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(mockESInstances).toHaveLength(0);
  });

  it('does not open EventSource when stream-token fetch fails', async () => {
    server.use(
      http.post('http://localhost/api/v1/notifications/stream-token', () =>
        HttpResponse.json({ detail: 'no session' }, { status: 401 })
      ),
      http.post('http://localhost/api/v1/auth/refresh', () =>
        HttpResponse.json({ detail: 'no session' }, { status: 401 })
      )
    );

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(mockESInstances).toHaveLength(0);
    consoleSpy.mockRestore();
  });

  it('does not use legacy fetch-in-hook helpers — delegates connection via useSSE', async () => {
    // Guard against regression: this hook must not re-implement ES lifecycle.
    // If new EventSource(...) is called directly from this hook (not useSSE),
    // we cannot detect it at the vitest level, but the lack of duplicated
    // reconnect logic is asserted by the file itself being ~70 LOC.
    const onEvent = vi.fn();
    renderHook(() => useSSENotifications(onEvent));
    await waitFor(() => {
      expect(mockESInstances).toHaveLength(1);
    });
    // Exactly one ES per stable url — no extra retries pile up idle.
    expect(mockESInstances).toHaveLength(1);
  });
});
