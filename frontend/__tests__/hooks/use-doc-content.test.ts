import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useDocContent } from '@/hooks/use-doc-content';
import type { DocContent } from '@/lib/types/search';

const BASE = 'http://localhost';

const mockContent: DocContent = {
  doc_id: 'doc-1',
  title: 'API Reference',
  content_html: '<h1>API Reference</h1><p>Content here.</p>',
  url: 'https://docs.example.com/api',
  source_name: 'Example Docs',
  last_indexed_at: '2026-04-17T10:00:00Z',
  content_truncated: false,
};

function stubDocContent(docId: string, response: DocContent = mockContent, status = 200) {
  server.use(
    http.get(`${BASE}/api/v1/docs/${docId}/content`, () =>
      status === 200
        ? HttpResponse.json({ data: response })
        : HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status }),
    ),
  );
}

describe('useDocContent', () => {
  it('returns null when docId is null', () => {
    const { result } = renderHook(() => useDocContent(null));
    expect(result.current.content).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('fetches and returns doc content on success', async () => {
    stubDocContent('doc-1');
    const { result } = renderHook(() => useDocContent('doc-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.content).not.toBeNull();
    expect(result.current.content?.title).toBe('API Reference');
    expect(result.current.content?.source_name).toBe('Example Docs');
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure', async () => {
    stubDocContent('doc-bad', mockContent, 404);
    const { result } = renderHook(() => useDocContent('doc-bad'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.content).toBeNull();
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it('exposes content_truncated flag', async () => {
    const truncated: DocContent = { ...mockContent, content_truncated: true };
    stubDocContent('doc-trunc', truncated);
    const { result } = renderHook(() => useDocContent('doc-trunc'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.content?.content_truncated).toBe(true);
  });
});
