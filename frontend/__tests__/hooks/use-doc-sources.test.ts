import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

import { useDocSources } from '@/hooks/use-doc-sources';
import type { DocSource } from '@/lib/types/puppet';

const SOURCE_INDEXED: DocSource = {
  id: 'src-1',
  name: 'My Repo',
  source_type: 'github_repo',
  url: 'https://github.com/acme/repo',
  is_public: true,
  status: 'indexed',
  last_indexed_at: '2026-04-17T12:00:00Z',
  item_count: 42,
};

const SOURCE_PENDING: DocSource = {
  id: 'src-2',
  name: 'Pending Docs',
  source_type: 'url',
  url: 'https://docs.example.com',
  is_public: false,
  status: 'pending',
  last_indexed_at: null,
  item_count: null,
};

describe('useDocSources', () => {
  it('loads sources on mount', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/documentation-sources', () =>
        HttpResponse.json({ data: [SOURCE_INDEXED] })
      )
    );
    const { result } = renderHook(() => useDocSources());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.sources).toHaveLength(1);
    expect(result.current.sources[0]).toEqual(SOURCE_INDEXED);
  });

  it('sets error on fetch failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/documentation-sources', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'fail' } }, { status: 500 })
      )
    );
    const { result } = renderHook(() => useDocSources());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).not.toBeNull();
  });

  it('addSource POSTs and prepends new source to list', async () => {
    const newSource: DocSource = { ...SOURCE_PENDING, id: 'src-new' };
    server.use(
      http.get('http://localhost/api/v1/admin/documentation-sources', () =>
        HttpResponse.json({ data: [SOURCE_INDEXED] })
      ),
      http.post('http://localhost/api/v1/admin/documentation-sources', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>;
        expect(body['name']).toBe('Pending Docs');
        return HttpResponse.json({ data: newSource });
      })
    );
    const { result } = renderHook(() => useDocSources());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.addSource({
        workspace_id: 'ws-1',
        name: 'Pending Docs',
        source_type: 'url',
        url: 'https://docs.example.com',
        is_public: false,
      });
    });

    expect(result.current.sources).toHaveLength(2);
    expect(result.current.sources[0]).toEqual(newSource);
  });

  it('removeSource DELETEs and removes from list', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/documentation-sources', () =>
        HttpResponse.json({ data: [SOURCE_INDEXED, SOURCE_PENDING] })
      ),
      http.delete('http://localhost/api/v1/admin/documentation-sources/src-1', () =>
        new HttpResponse(null, { status: 204 })
      )
    );
    const { result } = renderHook(() => useDocSources());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.sources).toHaveLength(2);

    await act(async () => {
      await result.current.removeSource('src-1');
    });

    expect(result.current.sources).toHaveLength(1);
    expect(result.current.sources[0]!.id).toBe('src-2');
  });

  it('hasPolling is true when any source is pending or indexing', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/documentation-sources', () =>
        HttpResponse.json({ data: [SOURCE_INDEXED, SOURCE_PENDING] })
      )
    );
    const { result } = renderHook(() => useDocSources());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPolling).toBe(true);
  });

  it('hasPolling is false when all sources are stable', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/documentation-sources', () =>
        HttpResponse.json({ data: [SOURCE_INDEXED] })
      )
    );
    const { result } = renderHook(() => useDocSources());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPolling).toBe(false);
  });
});
