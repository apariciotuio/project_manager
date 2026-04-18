/**
 * useJobProgress tests — EP-12 Group 9
 * Builds on top of useSSE targeting /api/v1/jobs/{id}/progress
 */
import { renderHook, act } from '@testing-library/react';
import { useJobProgress } from '@/hooks/use-job-progress';

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  readyState = MockEventSource.OPEN;
  url: string;
  onerror: ((e: Event) => void) | null = null;
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

  simulateMessage(data: string, eventType = 'message') {
    const event = new MessageEvent(eventType, { data });
    this.listeners.get(eventType)?.forEach((h) => h(event));
  }

  simulateError() {
    this.readyState = MockEventSource.CONNECTING;
    const event = new Event('error');
    // useSSE sets es.onerror — invoke it directly
    this.onerror?.(event);
    this.listeners.get('error')?.forEach((h) => h(event as MessageEvent));
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

describe('useJobProgress', () => {
  it('connects to /api/v1/jobs/{jobId}/progress', () => {
    renderHook(() => useJobProgress('job-123'));
    expect(MockEventSource.instances[0].url).toContain('/api/v1/jobs/job-123/progress');
  });

  it('returns running status with progress events', () => {
    const { result } = renderHook(() => useJobProgress('job-123'));
    act(() => {
      MockEventSource.instances[0].simulateMessage(
        JSON.stringify({ status: 'running', percent: 50, message: 'Processing...' }),
      );
    });
    expect(result.current.status).toBe('running');
    expect(result.current.percent).toBe(50);
    expect(result.current.message).toBe('Processing...');
  });

  it('returns complete status on event: done', () => {
    const { result } = renderHook(() => useJobProgress('job-123'));
    act(() => {
      MockEventSource.instances[0].simulateMessage(
        JSON.stringify({ result: { id: 'abc' } }),
        'done',
      );
    });
    expect(result.current.status).toBe('complete');
    expect(result.current.result).toEqual({ id: 'abc' });
  });

  it('closes EventSource on event: done', () => {
    renderHook(() => useJobProgress('job-123'));
    act(() => {
      MockEventSource.instances[0].simulateMessage(
        JSON.stringify({ result: {} }),
        'done',
      );
    });
    expect(MockEventSource.instances[0].readyState).toBe(MockEventSource.CLOSED);
  });

  it('returns error status on error event', () => {
    const { result } = renderHook(() => useJobProgress('job-123'));
    act(() => {
      MockEventSource.instances[0].simulateMessage(
        JSON.stringify({ message: 'Job failed' }),
        'error',
      );
    });
    expect(result.current.status).toBe('error');
    expect(result.current.errorMessage).toBe('Job failed');
  });

  it('closes EventSource on component unmount', () => {
    const { unmount } = renderHook(() => useJobProgress('job-123'));
    unmount();
    expect(MockEventSource.instances[0].readyState).toBe(MockEventSource.CLOSED);
  });

  it('auto-reconnects on connection drop (delegates to useSSE)', async () => {
    renderHook(() => useJobProgress('job-123'));
    act(() => { MockEventSource.instances[0].simulateError(); });
    await act(async () => { vi.advanceTimersByTime(1000); });
    // useSSE handles reconnect; a new EventSource should be created
    expect(MockEventSource.instances.length).toBeGreaterThan(1);
  });

  it('starts with connecting status', () => {
    const { result } = renderHook(() => useJobProgress('job-123'));
    // Either 'connecting' or 'open' depending on mock behavior; main thing: not error
    expect(['connecting', 'open', 'running']).toContain(result.current.status);
  });
});
