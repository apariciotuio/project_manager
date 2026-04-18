import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useRelatedDocs } from '@/hooks/use-related-docs';
import type { RelatedDoc } from '@/lib/types/search';

const BASE = 'http://localhost';

const mockDocs: RelatedDoc[] = Array.from({ length: 7 }, (_, i) => ({
  doc_id: `doc-${i + 1}`,
  title: `Document ${i + 1}`,
  source_name: 'Confluence',
  snippet: `Snippet for doc ${i + 1}`,
  url: `https://wiki.example.com/doc-${i + 1}`,
  score: 0.9 - i * 0.05,
}));

function stubRelatedDocs(workItemId: string, docs: RelatedDoc[] = mockDocs, status = 200) {
  server.use(
    http.get(`${BASE}/api/v1/work-items/${workItemId}/related-docs`, () =>
      status === 200
        ? HttpResponse.json({ data: docs })
        : HttpResponse.json({ error: { code: 'UPSTREAM_ERROR', message: 'Puppet unavailable' } }, { status }),
    ),
  );
}

describe('useRelatedDocs', () => {
  it('returns empty array when workItemId is null', () => {
    const { result } = renderHook(() => useRelatedDocs(null));
    expect(result.current.docs).toHaveLength(0);
    expect(result.current.isLoading).toBe(false);
  });

  it('fetches related docs on success', async () => {
    stubRelatedDocs('wi-1', mockDocs.slice(0, 3));
    const { result } = renderHook(() => useRelatedDocs('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.docs).toHaveLength(3);
    expect(result.current.docs[0]?.title).toBe('Document 1');
    expect(result.current.error).toBeNull();
  });

  it('caps results at 5 even if API returns more', async () => {
    stubRelatedDocs('wi-2', mockDocs); // 7 docs
    const { result } = renderHook(() => useRelatedDocs('wi-2'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.docs).toHaveLength(5);
  });

  it('sets error on 503, returns empty docs', async () => {
    stubRelatedDocs('wi-3', mockDocs, 503);
    const { result } = renderHook(() => useRelatedDocs('wi-3'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.docs).toHaveLength(0);
    expect(result.current.error).toBeInstanceOf(Error);
  });
});
