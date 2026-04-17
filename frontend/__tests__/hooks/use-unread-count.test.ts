import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useUnreadCount } from '@/hooks/use-unread-count';

describe('useUnreadCount', () => {
  beforeEach(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  });

  afterEach(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  });

  it('fetches count on mount', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 7 } })
      )
    );

    const { result } = renderHook(() => useUnreadCount());
    await waitFor(() => expect(result.current.count).toBe(7));
    expect(result.current.error).toBeNull();
  });

  it('count defaults to 0 before first fetch resolves', () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', async () => {
        await new Promise(() => {});
        return HttpResponse.json({ data: { count: 5 } });
      })
    );

    const { result } = renderHook(() => useUnreadCount());
    expect(result.current.count).toBe(0);
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure, count stays 0', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'oops' } }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useUnreadCount());
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    expect(result.current.count).toBe(0);
  });

  it('refetch() triggers a new API call', async () => {
    let callCount = 0;
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () => {
        callCount += 1;
        return HttpResponse.json({ data: { count: callCount * 3 } });
      })
    );

    const { result } = renderHook(() => useUnreadCount());
    await waitFor(() => expect(callCount).toBeGreaterThanOrEqual(1));
    const countBefore = callCount;
    const valueBefore = result.current.count;

    await act(async () => {
      result.current.refetch();
    });

    await waitFor(() => expect(callCount).toBeGreaterThan(countBefore));
    await waitFor(() => expect(result.current.count).toBeGreaterThan(valueBefore));
  });

  it('registers a 30s polling interval on mount', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      )
    );

    renderHook(() => useUnreadCount());

    const calls = setIntervalSpy.mock.calls;
    const pollCall = calls.find((args) => args[1] === 30_000);
    expect(pollCall).toBeDefined();

    setIntervalSpy.mockRestore();
  });

  it('clears interval on unmount', () => {
    const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      )
    );

    const { unmount } = renderHook(() => useUnreadCount());
    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });

  it('registers visibilitychange listener on mount', () => {
    const addEventListenerSpy = vi.spyOn(document, 'addEventListener');

    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () =>
        HttpResponse.json({ data: { count: 0 } })
      )
    );

    renderHook(() => useUnreadCount());

    const visibilityCalls = addEventListenerSpy.mock.calls.filter(
      (args) => args[0] === 'visibilitychange'
    );
    expect(visibilityCalls.length).toBeGreaterThan(0);

    addEventListenerSpy.mockRestore();
  });

  it('dispatching visibilitychange when visible triggers a refetch', async () => {
    let callCount = 0;
    server.use(
      http.get('http://localhost/api/v1/notifications/unread-count', () => {
        callCount += 1;
        return HttpResponse.json({ data: { count: callCount } });
      })
    );

    const { result } = renderHook(() => useUnreadCount());
    await waitFor(() => expect(callCount).toBeGreaterThanOrEqual(1));
    const countBefore = callCount;

    // Simulate becoming visible
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await waitFor(() => expect(callCount).toBeGreaterThan(countBefore));
    expect(result.current.count).toBeGreaterThan(0);
  });
});
