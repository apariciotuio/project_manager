/**
 * EP-07 FE — useSectionComments hook.
 *
 * 2.7 [RED] Tests:
 * - fetches section-anchored comments on mount
 * - passes section_id as filter param to the API
 * - error state populated on failure
 * - returns empty list when no comments for section
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({ useTranslations: () => (k: string) => k }));

const BASE = 'http://localhost';

const SECTION_COMMENT = {
  id: 'cmt-sec-1',
  work_item_id: 'wi-1',
  parent_comment_id: null,
  body: 'Section comment',
  actor_type: 'human',
  actor_id: 'user-1',
  anchor_section_id: 'sec-abc',
  anchor_start_offset: 10,
  anchor_end_offset: 20,
  anchor_snapshot_text: 'some text',
  anchor_status: 'active',
  is_edited: false,
  deleted_at: null,
  created_at: '2026-01-01T00:00:00Z',
  replies: [],
};

describe('useSectionComments', () => {
  beforeEach(() => {
    server.use(
      http.get(
        `${BASE}/api/v1/work-items/wi-1/sections/sec-abc/comments`,
        () => HttpResponse.json({ data: [SECTION_COMMENT] }),
      ),
      http.get(
        `${BASE}/api/v1/work-items/wi-1/sections/sec-empty/comments`,
        () => HttpResponse.json({ data: [] }),
      ),
    );
  });

  it('fetches section comments on mount', async () => {
    const { useSectionComments } = await import(
      '@/hooks/work-item/use-section-comments'
    );
    const { result } = renderHook(() =>
      useSectionComments('wi-1', 'sec-abc'),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.comments).toHaveLength(1);
    expect(result.current.comments[0]?.id).toBe('cmt-sec-1');
  });

  it('passes section_id in the URL path to the API', async () => {
    let capturedUrl = '';
    server.use(
      http.get(
        `${BASE}/api/v1/work-items/wi-1/sections/sec-xyz/comments`,
        ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json({ data: [] });
        },
      ),
    );

    const { useSectionComments } = await import(
      '@/hooks/work-item/use-section-comments'
    );
    const { result } = renderHook(() =>
      useSectionComments('wi-1', 'sec-xyz'),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(capturedUrl).toContain('/sections/sec-xyz/comments');
  });

  it('returns empty list when no comments for section', async () => {
    const { useSectionComments } = await import(
      '@/hooks/work-item/use-section-comments'
    );
    const { result } = renderHook(() =>
      useSectionComments('wi-1', 'sec-empty'),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.comments).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });

  it('exposes error on API failure', async () => {
    server.use(
      http.get(
        `${BASE}/api/v1/work-items/wi-fail/sections/sec-abc/comments`,
        () =>
          HttpResponse.json(
            { error: { message: 'Not found' } },
            { status: 404 },
          ),
      ),
    );

    const { useSectionComments } = await import(
      '@/hooks/work-item/use-section-comments'
    );
    const { result } = renderHook(() =>
      useSectionComments('wi-fail', 'sec-abc'),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).not.toBeNull();
    expect(result.current.comments).toHaveLength(0);
  });
});
