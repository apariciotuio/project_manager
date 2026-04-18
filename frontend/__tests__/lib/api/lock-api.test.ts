/**
 * EP-17 — lock-api.ts unit tests.
 * Covers acquire, heartbeat, release, force-release, list endpoints.
 */
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import {
  acquireSectionLock,
  heartbeatSectionLock,
  releaseSectionLock,
  forceReleaseSectionLock,
  listWorkItemLocks,
} from '@/lib/api/lock-api';

const LOCK_DTO = {
  id: 'lock-1',
  section_id: 'sec-1',
  work_item_id: 'wi-1',
  held_by: 'user-1',
  acquired_at: '2026-04-18T09:00:00.000Z',
  heartbeat_at: '2026-04-18T09:00:00.000Z',
  expires_at: '2026-04-18T09:05:00.000Z',
};

describe('acquireSectionLock', () => {
  it('returns lock DTO on 201', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock', () =>
        HttpResponse.json({ data: LOCK_DTO, message: 'lock acquired' }, { status: 201 })
      )
    );
    const result = await acquireSectionLock('sec-1');
    expect(result.id).toBe('lock-1');
    expect(result.section_id).toBe('sec-1');
    expect(result.held_by).toBe('user-1');
  });

  it('returns refreshed lock when same user re-acquires (200)', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock', () =>
        HttpResponse.json({ data: LOCK_DTO, message: 'lock refreshed' }, { status: 201 })
      )
    );
    const result = await acquireSectionLock('sec-1');
    expect(result.expires_at).toBe(LOCK_DTO.expires_at);
  });

  it('throws on 409 conflict (held by another user)', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-2/lock', () =>
        HttpResponse.json(
          { error: { code: 'LOCK_CONFLICT', message: 'section is locked', details: { held_by: 'user-2' } } },
          { status: 409 }
        )
      )
    );
    await expect(acquireSectionLock('sec-2')).rejects.toBeDefined();
  });

  it('throws on 404 section not found', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/missing/lock', () =>
        HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'section not found', details: {} } },
          { status: 404 }
        )
      )
    );
    await expect(acquireSectionLock('missing')).rejects.toBeDefined();
  });
});

describe('heartbeatSectionLock', () => {
  it('returns updated lock with refreshed expires_at', async () => {
    const refreshed = { ...LOCK_DTO, heartbeat_at: '2026-04-18T09:00:30.000Z', expires_at: '2026-04-18T09:05:30.000Z' };
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/heartbeat', () =>
        HttpResponse.json({ data: refreshed, message: 'heartbeat ok' })
      )
    );
    const result = await heartbeatSectionLock('sec-1');
    expect(result.heartbeat_at).toBe('2026-04-18T09:00:30.000Z');
    expect(result.expires_at).toBe('2026-04-18T09:05:30.000Z');
  });

  it('throws 404 when lock not found', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-gone/lock/heartbeat', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'lock not found', details: {} } }, { status: 404 })
      )
    );
    await expect(heartbeatSectionLock('sec-gone')).rejects.toBeDefined();
  });

  it('throws 403 when lock held by another user', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-stolen/lock/heartbeat', () =>
        HttpResponse.json({ error: { code: 'LOCK_FORBIDDEN', message: 'forbidden', details: {} } }, { status: 403 })
      )
    );
    await expect(heartbeatSectionLock('sec-stolen')).rejects.toBeDefined();
  });
});

describe('releaseSectionLock', () => {
  it('resolves on 200', async () => {
    server.use(
      http.delete('http://localhost/api/v1/sections/sec-1/lock', () =>
        HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'lock released' })
      )
    );
    await expect(releaseSectionLock('sec-1')).resolves.toBeUndefined();
  });

  it('throws 403 if not lock holder', async () => {
    server.use(
      http.delete('http://localhost/api/v1/sections/sec-other/lock', () =>
        HttpResponse.json({ error: { code: 'LOCK_FORBIDDEN', message: 'forbidden', details: {} } }, { status: 403 })
      )
    );
    await expect(releaseSectionLock('sec-other')).rejects.toBeDefined();
  });
});

describe('forceReleaseSectionLock', () => {
  it('resolves on success', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-1/lock/force-release', () =>
        HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'lock force-released' })
      )
    );
    await expect(forceReleaseSectionLock('sec-1')).resolves.toBeUndefined();
  });

  it('throws 404 when no lock exists', async () => {
    server.use(
      http.post('http://localhost/api/v1/sections/sec-none/lock/force-release', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'lock not found', details: {} } }, { status: 404 })
      )
    );
    await expect(forceReleaseSectionLock('sec-none')).rejects.toBeDefined();
  });
});

describe('listWorkItemLocks', () => {
  it('returns list of section lock summaries', async () => {
    const summaries = [
      { section_id: 'sec-1', locked_by: 'user-1', locked_by_name: 'Ana García', locked_at: '2026-04-18T09:00:00.000Z' },
      { section_id: 'sec-2', locked_by: 'user-2', locked_by_name: null, locked_at: '2026-04-18T09:01:00.000Z' },
    ];
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/locks', () =>
        HttpResponse.json({ data: summaries, message: 'ok' })
      )
    );
    const result = await listWorkItemLocks('wi-1');
    expect(result).toHaveLength(2);
    expect(result[0]!.section_id).toBe('sec-1');
    expect(result[1]!.locked_by_name).toBeNull();
  });

  it('returns empty array when no active locks', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-empty/locks', () =>
        HttpResponse.json({ data: [], message: 'ok' })
      )
    );
    const result = await listWorkItemLocks('wi-empty');
    expect(result).toHaveLength(0);
  });
});
