/**
 * EP-07 Group 1 — API client tests for versions, comments, timeline.
 */

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import {
  getVersionDiff,
  getArbitraryDiff,
  createComment,
  listTimeline,
} from '@/lib/api/versions';
import type { VersionDiff } from '@/lib/types/versions';

const BASE = 'http://localhost';

const mockDiff: VersionDiff = {
  from_version: 1,
  to_version: 2,
  metadata_diff: {},
  sections: [
    {
      section_type: 'summary',
      change_type: 'modified',
      hunks: [
        { type: 'removed', lines: ['Old summary'] },
        { type: 'added', lines: ['New summary'] },
      ],
    },
  ],
};

// ─── getVersionDiff ─────────────────────────────────────────────────────────

describe('getVersionDiff', () => {
  it('maps server response to VersionDiff type', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions/2/diff`, () =>
        HttpResponse.json({ data: mockDiff }),
      ),
    );

    const result = await getVersionDiff('wi-1', 2);

    expect(result.from_version).toBe(1);
    expect(result.to_version).toBe(2);
    expect(result.sections).toHaveLength(1);
    expect(result.sections[0]?.section_type).toBe('summary');
    expect(result.sections[0]?.change_type).toBe('modified');
    expect(result.sections[0]?.hunks).toHaveLength(2);
  });

  it('propagates server error as-is', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions/99/diff`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'not found' } }, { status: 404 }),
      ),
    );

    await expect(getVersionDiff('wi-1', 99)).rejects.toThrow();
  });
});

// ─── getArbitraryDiff ────────────────────────────────────────────────────────

describe('getArbitraryDiff', () => {
  it('maps server response to VersionDiff type', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions/diff`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('from')).toBe('1');
        expect(url.searchParams.get('to')).toBe('2');
        return HttpResponse.json({ data: mockDiff });
      }),
    );

    const result = await getArbitraryDiff('wi-1', 1, 2);

    expect(result.from_version).toBe(1);
    expect(result.to_version).toBe(2);
  });

  it('rejects with INVALID_DIFF_RANGE when from > to (no network call)', async () => {
    let networkCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions/diff`, () => {
        networkCalled = true;
        return HttpResponse.json({ data: mockDiff });
      }),
    );

    await expect(getArbitraryDiff('wi-1', 5, 3)).rejects.toMatchObject({
      code: 'INVALID_DIFF_RANGE',
    });
    expect(networkCalled).toBe(false);
  });

  it('rejects with INVALID_DIFF_RANGE when from === to', async () => {
    await expect(getArbitraryDiff('wi-1', 3, 3)).rejects.toMatchObject({
      code: 'INVALID_DIFF_RANGE',
    });
  });

  it('propagates server 400 for other reasons', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions/diff`, () =>
        HttpResponse.json({ error: { code: 'BAD_REQUEST', message: 'bad' } }, { status: 400 }),
      ),
    );

    await expect(getArbitraryDiff('wi-1', 1, 2)).rejects.toThrow();
  });
});

// ─── createComment ───────────────────────────────────────────────────────────

describe('createComment', () => {
  const mockComment = {
    id: 'cmt-1',
    work_item_id: 'wi-1',
    parent_comment_id: null,
    body: 'Hello',
    actor_type: 'human',
    actor_id: 'user-1',
    anchor_section_id: null,
    anchor_start_offset: null,
    anchor_end_offset: null,
    anchor_snapshot_text: null,
    anchor_status: 'active',
    is_edited: false,
    deleted_at: null,
    created_at: '2026-04-18T10:00:00Z',
    replies: [],
  };

  it('creates a general comment and returns Comment', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json({ data: mockComment }, { status: 201 }),
      ),
    );

    const result = await createComment('wi-1', { body: 'Hello' });

    expect(result.id).toBe('cmt-1');
    expect(result.body).toBe('Hello');
    expect(result.anchor_section_id).toBeNull();
  });

  it('creates an anchored comment', async () => {
    const anchored = {
      ...mockComment,
      anchor_section_id: 'sec-1',
      anchor_start_offset: 0,
      anchor_end_offset: 5,
      anchor_snapshot_text: 'Hello',
    };

    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json({ data: anchored }, { status: 201 }),
      ),
    );

    const result = await createComment('wi-1', {
      body: 'Hello',
      anchor_section_id: 'sec-1',
      anchor_start_offset: 0,
      anchor_end_offset: 5,
      anchor_snapshot_text: 'Hello',
    });

    expect(result.anchor_section_id).toBe('sec-1');
    expect(result.anchor_start_offset).toBe(0);
  });

  it('rejects with INVALID_ANCHOR_RANGE when start > end (no network call)', async () => {
    let networkCalled = false;
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/comments`, () => {
        networkCalled = true;
        return HttpResponse.json({ data: mockComment }, { status: 201 });
      }),
    );

    await expect(
      createComment('wi-1', {
        body: 'Hello',
        anchor_section_id: 'sec-1',
        anchor_start_offset: 10,
        anchor_end_offset: 5,
      }),
    ).rejects.toMatchObject({ code: 'INVALID_ANCHOR_RANGE' });

    expect(networkCalled).toBe(false);
  });

  it('propagates server 422 for other validation errors', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json(
          { error: { code: 'VALIDATION_ERROR', message: 'body too long' } },
          { status: 422 },
        ),
      ),
    );

    await expect(createComment('wi-1', { body: 'x'.repeat(10001) })).rejects.toThrow();
  });
});

// ─── listTimeline ────────────────────────────────────────────────────────────

describe('listTimeline', () => {
  const mockEvent = {
    id: 'ev-1',
    event_type: 'state_transition',
    actor_type: 'human',
    actor_id: 'user-1',
    actor_display_name: 'Alice',
    summary: 'State changed',
    payload: {},
    occurred_at: '2026-04-18T10:00:00Z',
    source_id: null,
    source_table: null,
  };

  it('fetches first page without filters', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/timeline`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('limit')).toBeTruthy();
        return HttpResponse.json({
          data: { events: [mockEvent], has_more: false, next_cursor: null },
        });
      }),
    );

    const result = await listTimeline('wi-1', {});

    expect(result.data.events).toHaveLength(1);
    expect(result.data.has_more).toBe(false);
    expect(result.data.next_cursor).toBeNull();
  });

  it('serializes event_type filter param correctly', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/timeline`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('event_type')).toBe('state_transition');
        return HttpResponse.json({
          data: { events: [mockEvent], has_more: false, next_cursor: null },
        });
      }),
    );

    await listTimeline('wi-1', { event_type: 'state_transition' });
  });

  it('passes cursor param for pagination', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/timeline`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('cursor')).toBe('abc123');
        return HttpResponse.json({
          data: { events: [], has_more: false, next_cursor: null },
        });
      }),
    );

    await listTimeline('wi-1', { cursor: 'abc123' });
  });

  it('passes actor_type filter param', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/timeline`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('actor_type')).toBe('human');
        return HttpResponse.json({
          data: { events: [], has_more: false, next_cursor: null },
        });
      }),
    );

    await listTimeline('wi-1', { actor_type: 'human' });
  });
});
