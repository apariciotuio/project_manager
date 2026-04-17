import { describe, it, expect, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useTemplates } from '@/hooks/use-templates';

describe('useTemplates', () => {
  it('returns templates on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/templates', () =>
        HttpResponse.json({
          data: [
            { id: 't1', name: 'Bug Report', description: null, type: 'bug', fields: {} },
            { id: 't2', name: 'Feature', description: 'New feature', type: 'enhancement', fields: {} },
          ],
        })
      )
    );

    const { result } = renderHook(() => useTemplates());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.templates).toHaveLength(2);
    expect(result.current.templates[0]!.name).toBe('Bug Report');
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/templates', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'boom' } }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useTemplates());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.templates).toHaveLength(0);
  });

  it('starts with isLoading=true', () => {
    server.use(
      http.get('http://localhost/api/v1/templates', async () => {
        await new Promise(() => {}); // never resolves
        return HttpResponse.json({ data: [] });
      })
    );

    const { result } = renderHook(() => useTemplates());
    expect(result.current.isLoading).toBe(true);
  });
});
