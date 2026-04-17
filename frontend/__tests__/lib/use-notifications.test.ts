import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useNotifications } from '@/hooks/use-notifications';

describe('useNotifications', () => {
  it('returns loading=true initially', () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 20 } }),
      ),
    );
    const { result } = renderHook(() => useNotifications());
    expect(result.current.isLoading).toBe(true);
  });

  it('returns unreadCount equal to array length', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [{ id: '1' }, { id: '2' }, { id: '3' }], total: 3, page: 1, page_size: 20 } }),
      ),
    );
    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.unreadCount).toBe(3);
  });

  it('returns unreadCount 0 on empty array', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 20 } }),
      ),
    );
    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.unreadCount).toBe(0);
  });

  it('returns unreadCount 0 on API error (fail safe)', async () => {
    server.use(
      http.get('http://localhost/api/v1/notifications', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'oops' } }, { status: 500 }),
      ),
    );
    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.unreadCount).toBe(0);
  });
});
