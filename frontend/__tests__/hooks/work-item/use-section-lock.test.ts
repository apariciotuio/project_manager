/**
 * EP-17 — useSectionLock hook tests.
 * Tests acquire, heartbeat lifecycle, release, and lock-loss scenarios.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useSectionLock, LOCK_HEARTBEAT_INTERVAL_MS } from '@/hooks/work-item/use-section-lock';

const LOCK_DTO = {
  id: 'lock-1',
  section_id: 'sec-1',
  work_item_id: 'wi-1',
  held_by: 'user-1',
  acquired_at: '2026-04-18T09:00:00.000Z',
  heartbeat_at: '2026-04-18T09:00:00.000Z',
  expires_at: '2026-04-18T09:05:00.000Z',
};

function acquireOk() {
  server.use(
    http.post('http://localhost/api/v1/sections/sec-1/lock', () =>
      HttpResponse.json({ data: LOCK_DTO, message: 'lock acquired' }, { status: 201 })
    )
  );
}

function heartbeatOk() {
  const refreshed = { ...LOCK_DTO, heartbeat_at: '2026-04-18T09:00:30.000Z', expires_at: '2026-04-18T09:05:30.000Z' };
  server.use(
    http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () =>
      HttpResponse.json({ data: refreshed, message: 'heartbeat ok' })
    )
  );
}

function releaseOk() {
  server.use(
    http.delete('http://localhost/api/v1/sections/sec-1/lock', () =>
      HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'lock released' })
    )
  );
}

describe('useSectionLock', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts with no lock and isHolder=false', () => {
    server.use(
      http.delete('http://localhost/api/v1/sections/sec-1/lock', () =>
        HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'ok' })
      )
    );
    const { result } = renderHook(() => useSectionLock('sec-1'));
    expect(result.current.lock).toBeNull();
    expect(result.current.isHolder).toBe(false);
    expect(result.current.lockLost).toBe(false);
  });

  it('acquires lock and sets isHolder=true', async () => {
    acquireOk();
    releaseOk();
    heartbeatOk();

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    expect(result.current.isHolder).toBe(true);
    expect(result.current.lock?.id).toBe('lock-1');
    expect(result.current.lockLost).toBe(false);
  });

  it('starts heartbeat interval after acquire', async () => {
    acquireOk();
    releaseOk();
    const heartbeatCalled = vi.fn();
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () => {
        heartbeatCalled();
        return HttpResponse.json({ data: LOCK_DTO, message: 'heartbeat ok' });
      })
    );

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    // Advance past one heartbeat interval
    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      await Promise.resolve();
    });

    expect(heartbeatCalled).toHaveBeenCalledTimes(1);
  });

  it('releases lock and sets isHolder=false', async () => {
    acquireOk();
    releaseOk();
    heartbeatOk();

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });
    expect(result.current.isHolder).toBe(true);

    await act(async () => {
      await result.current.releaseLock();
    });

    expect(result.current.isHolder).toBe(false);
    expect(result.current.lock).toBeNull();
  });

  it('sets lockLost=true on heartbeat 404', async () => {
    acquireOk();
    releaseOk();
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () =>
        HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'lock not found', details: {} } },
          { status: 404 }
        )
      )
    );

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      // Flush the async heartbeat callback
      await vi.runAllTimersAsync();
    });

    expect(result.current.lockLost).toBe(true);
    expect(result.current.isHolder).toBe(false);
    expect(result.current.lockLostReason).toBe('expired');
  });

  it('sets lockLost=true on heartbeat 403', async () => {
    acquireOk();
    releaseOk();
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () =>
        HttpResponse.json(
          { error: { code: 'LOCK_FORBIDDEN', message: 'forbidden', details: {} } },
          { status: 403 }
        )
      )
    );

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      await vi.runAllTimersAsync();
    });

    expect(result.current.lockLost).toBe(true);
    expect(result.current.lockLostReason).toBe('expired');
  });

  it('does not set lockLost on 503 heartbeat (connection issue)', async () => {
    acquireOk();
    releaseOk();
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () =>
        HttpResponse.json({}, { status: 503 })
      )
    );

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      await Promise.resolve();
    });

    // lockLost stays false on 503 — interval continues
    expect(result.current.lockLost).toBe(false);
    expect(result.current.isHolder).toBe(true);
  });

  it('does not release lock if already lockLost on releaseLock call', async () => {
    acquireOk();
    const deleteCalled = vi.fn();
    server.use(
      http.delete('http://localhost/api/v1/sections/sec-1/lock', () => {
        deleteCalled();
        return HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'ok' });
      })
    );
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () =>
        HttpResponse.json({}, { status: 404 })
      )
    );

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    // Trigger lock loss
    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      await vi.runAllTimersAsync();
    });

    expect(result.current.lockLost).toBe(true);

    // Now call releaseLock — should NOT call DELETE
    await act(async () => {
      await result.current.releaseLock();
    });

    expect(deleteCalled).not.toHaveBeenCalled();
  });

  it('stops heartbeat after lockLost (no further heartbeat calls)', async () => {
    acquireOk();
    releaseOk();
    let heartbeatCallCount = 0;
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () => {
        heartbeatCallCount++;
        // All calls return 404 → lock lost on first call, interval cleared
        return HttpResponse.json({}, { status: 404 });
      })
    );

    const { result } = renderHook(() => useSectionLock('sec-1'));

    await act(async () => {
      await result.current.acquireLock();
    });

    // First heartbeat — triggers lock lost
    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      await vi.runAllTimersAsync();
    });

    expect(result.current.lockLost).toBe(true);
    const countAfterLoss = heartbeatCallCount;

    // Advance another interval — no additional heartbeat should fire
    await act(async () => {
      vi.advanceTimersByTime(LOCK_HEARTBEAT_INTERVAL_MS + 100);
      await vi.runAllTimersAsync();
    });

    expect(heartbeatCallCount).toBe(countAfterLoss);
  });
});
