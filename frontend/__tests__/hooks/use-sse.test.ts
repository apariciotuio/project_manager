/**
 * useSSE hook tests — EP-12 Group 9
 * Tests shared SSE infrastructure — all SSE consumers delegate to this.
 */
import { renderHook, act } from '@testing-library/react';
import { useSSE } from '@/hooks/use-sse';

// Minimal EventSource mock
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  readyState = MockEventSource.OPEN;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onopen: ((e: Event) => void) | null = null;
  url: string;

  private listeners: Map<string, ((e: MessageEvent) => void)[]> = new Map();

  static instances: MockEventSource[] = [];

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type)!.push(handler);
  }

  removeEventListener(type: string, handler: (e: MessageEvent) => void) {
    const handlers = this.listeners.get(type) ?? [];
    this.listeners.set(type, handlers.filter((h) => h !== handler));
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  // Test helpers
  simulateMessage(data: string, eventType = 'message') {
    const event = new MessageEvent(eventType, { data });
    this.listeners.get(eventType)?.forEach((h) => h(event));
    if (eventType === 'message' && this.onmessage) this.onmessage(event);
  }

  simulateError() {
    this.readyState = MockEventSource.CONNECTING;
    const event = new Event('error');
    this.listeners.get('error')?.forEach((h) => h(event as MessageEvent));
    if (this.onerror) this.onerror(event);
  }

  simulateOpen() {
    this.readyState = MockEventSource.OPEN;
    const event = new Event('open');
    if (this.onopen) this.onopen(event);
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.useFakeTimers();
  // @ts-expect-error - mock EventSource
  global.EventSource = MockEventSource;
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('useSSE', () => {
  it('opens EventSource to the given URL', () => {
    const onMessage = vi.fn();
    renderHook(() => useSSE('http://localhost/api/v1/test', onMessage));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe('http://localhost/api/v1/test');
  });

  it('calls onMessage for each incoming event', () => {
    const onMessage = vi.fn();
    renderHook(() => useSSE('http://localhost/api/v1/test', onMessage));
    const es = MockEventSource.instances[0];
    act(() => {
      es.simulateMessage('{"type":"progress","percent":50}');
    });
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage.mock.calls[0][0]).toBeInstanceOf(MessageEvent);
    expect(onMessage.mock.calls[0][0].data).toBe('{"type":"progress","percent":50}');
  });

  it('returns status=open after connection', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useSSE('http://localhost/api/v1/test', onMessage));
    expect(result.current.status).toBe('open');
  });

  it('closes EventSource on unmount', () => {
    const onMessage = vi.fn();
    const { unmount } = renderHook(() => useSSE('http://localhost/api/v1/test', onMessage));
    unmount();
    expect(MockEventSource.instances[0].readyState).toBe(MockEventSource.CLOSED);
  });

  it('does not call onMessage after unmount', () => {
    const onMessage = vi.fn();
    const { unmount } = renderHook(() => useSSE('http://localhost/api/v1/test', onMessage));
    unmount();
    const es = MockEventSource.instances[0];
    act(() => {
      es.simulateMessage('late message');
    });
    expect(onMessage).not.toHaveBeenCalled();
  });

  it('reconnects with exponential backoff on error (1s, 2s, 4s)', async () => {
    const onMessage = vi.fn();
    renderHook(() => useSSE('http://localhost/api/v1/test', onMessage));
    const es1 = MockEventSource.instances[0];

    // First error — should reconnect after 1s
    act(() => { es1.simulateError(); });
    expect(MockEventSource.instances).toHaveLength(1);

    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(MockEventSource.instances).toHaveLength(2);

    // Second error — should reconnect after 2s
    const es2 = MockEventSource.instances[1];
    act(() => { es2.simulateError(); });
    await act(async () => { vi.advanceTimersByTime(2000); });
    expect(MockEventSource.instances).toHaveLength(3);
  });

  it('returns status=error after all retries exhausted', async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useSSE('http://localhost/api/v1/test', onMessage, { maxRetries: 2, baseDelay: 100 }),
    );

    act(() => { MockEventSource.instances[0].simulateError(); });
    await act(async () => { vi.advanceTimersByTime(100); });

    act(() => { MockEventSource.instances[1].simulateError(); });
    await act(async () => { vi.advanceTimersByTime(200); });

    act(() => { MockEventSource.instances[2].simulateError(); });
    // No more retries
    await act(async () => { vi.advanceTimersByTime(1000); });

    expect(result.current.status).toBe('error');
    expect(MockEventSource.instances).toHaveLength(3);
  });

  it('calls onBeforeReconnect before each reconnect attempt', async () => {
    const onMessage = vi.fn();
    const onBeforeReconnect = vi.fn();
    renderHook(() =>
      useSSE('http://localhost/api/v1/test', onMessage, {
        maxRetries: 1,
        baseDelay: 100,
        onBeforeReconnect,
      }),
    );

    act(() => { MockEventSource.instances[0].simulateError(); });
    await act(async () => { vi.advanceTimersByTime(100); });

    expect(onBeforeReconnect).toHaveBeenCalledTimes(1);
  });
});
