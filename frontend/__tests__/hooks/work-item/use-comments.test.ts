/**
 * EP-07 FE — useComments hook.
 *
 * 2.5 [RED] Tests:
 * - fetches list on mount
 * - addComment appends optimistically before server responds
 * - addComment rolls back optimistic item on server error
 * - deleteComment removes optimistically before server responds
 * - deleteComment rolls back on server error
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({ useTranslations: () => (k: string) => k }));

const BASE = 'http://localhost';

const COMMENT_1 = {
  id: 'cmt-1',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'First comment',
  actor_type: 'human',
  actor_id: 'user-1',
  anchor_section_id: null,
  anchor_start_offset: null,
  anchor_end_offset: null,
  anchor_snapshot_text: null,
  anchor_status: 'active',
  is_edited: false,
  deleted_at: null,
  created_at: '2026-01-01T00:00:00Z',
  replies: [],
};

const COMMENT_2 = {
  id: 'cmt-2',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'Second comment',
  actor_type: 'human',
  actor_id: 'user-2',
  anchor_section_id: null,
  anchor_start_offset: null,
  anchor_end_offset: null,
  anchor_snapshot_text: null,
  anchor_status: 'active',
  is_edited: false,
  deleted_at: null,
  created_at: '2026-01-02T00:00:00Z',
  replies: [],
};

describe('useComments', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json({ data: [COMMENT_1] }),
      ),
    );
  });

  it('fetches comment list on mount', async () => {
    const { useComments } = await import('@/hooks/work-item/use-comments');
    const { result } = renderHook(() => useComments('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.comments).toHaveLength(1);
    expect(result.current.comments[0]?.id).toBe('cmt-1');
  });

  it('addComment appends optimistically before server responds', async () => {
    let resolvePost!: (value: Response) => void;
    const slowPost = new Promise<Response>((res) => { resolvePost = res; });

    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/comments`, () => slowPost),
    );

    const { useComments } = await import('@/hooks/work-item/use-comments');
    const { result } = renderHook(() => useComments('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.comments).toHaveLength(1);

    // Kick off addComment — do NOT await yet
    let addPromise: Promise<void>;
    act(() => {
      addPromise = result.current.addComment({ body: 'Second comment' });
    });

    // Optimistic item should appear immediately
    await waitFor(() => expect(result.current.comments).toHaveLength(2));
    expect(result.current.comments[1]?.body).toBe('Second comment');

    // Resolve the server — server returns the real comment
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json({ data: [COMMENT_1, COMMENT_2] }),
      ),
    );
    resolvePost(HttpResponse.json({ data: COMMENT_2 }) as unknown as Response);

    await act(async () => { await addPromise; });
    await waitFor(() =>
      expect(result.current.comments.find((c) => c.id === 'cmt-2')).toBeDefined(),
    );
  });

  it('addComment rolls back optimistic item on server error', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/wi-1/comments`, () =>
        HttpResponse.json({ error: { message: 'Server error' } }, { status: 500 }),
      ),
    );

    const { useComments } = await import('@/hooks/work-item/use-comments');
    const { result } = renderHook(() => useComments('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.comments).toHaveLength(1);

    await act(async () => {
      await result.current.addComment({ body: 'Will fail' }).catch(() => {});
    });

    // Optimistic item must be rolled back
    await waitFor(() => expect(result.current.comments).toHaveLength(1));
    expect(result.current.error).not.toBeNull();
  });

  it('deleteComment removes optimistically before server responds', async () => {
    server.use(
      http.delete(
        `${BASE}/api/v1/work-items/wi-1/comments/cmt-1`,
        async () => {
          await new Promise((res) => setTimeout(res, 50));
          return HttpResponse.json({}, { status: 204 });
        },
      ),
    );

    const { useComments } = await import('@/hooks/work-item/use-comments');
    const { result } = renderHook(() => useComments('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.comments).toHaveLength(1);

    act(() => {
      void result.current.deleteComment('cmt-1');
    });

    // Optimistic removal — item gone before server responds
    await waitFor(() => expect(result.current.comments).toHaveLength(0));
  });

  it('deleteComment rolls back on server error', async () => {
    server.use(
      http.delete(
        `${BASE}/api/v1/work-items/wi-1/comments/cmt-1`,
        () =>
          HttpResponse.json({ error: { message: 'Forbidden' } }, { status: 403 }),
      ),
    );

    const { useComments } = await import('@/hooks/work-item/use-comments');
    const { result } = renderHook(() => useComments('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.comments).toHaveLength(1);

    await act(async () => {
      await result.current.deleteComment('cmt-1').catch(() => {});
    });

    // Must roll back
    await waitFor(() => expect(result.current.comments).toHaveLength(1));
    expect(result.current.error).not.toBeNull();
  });
});
