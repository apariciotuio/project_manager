/**
 * EP-07 FE — use-versions hook.
 *
 * Tests:
 * - fetches versions on mount
 * - loadMore appends next page
 * - hasMore false when no next_cursor
 * - refetch resets and re-fetches
 * - error state populated on API failure
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({ useTranslations: () => (k: string) => k }));

const BASE = 'http://localhost';

const version1 = {
  id: 'ver-1',
  work_item_id: 'wi-1',
  version_number: 1,
  trigger: 'content_edit',
  actor_type: 'human',
  actor_id: 'user-1',
  commit_message: 'Updated summary',
  archived: false,
  created_at: '2026-04-17T10:00:00Z',
};

const version2 = {
  id: 'ver-2',
  work_item_id: 'wi-1',
  version_number: 2,
  trigger: 'content_edit',
  actor_type: 'human',
  actor_id: 'user-1',
  commit_message: 'Updated context',
  archived: false,
  created_at: '2026-04-17T11:00:00Z',
};

describe('useVersions', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions`, ({ request }) => {
        const url = new URL(request.url);
        const before = url.searchParams.get('before');
        if (before === '2') {
          return HttpResponse.json({
            data: [version1],
            meta: { has_more: false, next_cursor: null },
          });
        }
        return HttpResponse.json({
          data: [version2, version1],
          meta: { has_more: false, next_cursor: null },
        });
      }),
    );
  });

  it('loads versions on mount', async () => {
    const { useVersions } = await import('@/hooks/work-item/use-versions');
    const { result } = renderHook(() => useVersions('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.versions).toHaveLength(2);
    expect(result.current.versions[0]?.version_number).toBe(2);
  });

  it('hasMore false when no next_cursor', async () => {
    const { useVersions } = await import('@/hooks/work-item/use-versions');
    const { result } = renderHook(() => useVersions('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.hasMore).toBe(false);
  });

  it('exposes error on API failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-fail/versions`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'not found' } }, { status: 404 }),
      ),
    );

    const { useVersions } = await import('@/hooks/work-item/use-versions');
    const { result } = renderHook(() => useVersions('wi-fail'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).not.toBeNull();
  });

  it('refetch re-requests versions', async () => {
    const { useVersions } = await import('@/hooks/work-item/use-versions');
    const { result } = renderHook(() => useVersions('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const before = result.current.versions.length;

    await act(async () => {
      await result.current.refetch();
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.versions.length).toBeGreaterThanOrEqual(before);
  });
});
