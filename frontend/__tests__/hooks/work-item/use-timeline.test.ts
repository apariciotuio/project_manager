import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTimeline } from '@/hooks/work-item/use-timeline';

const PAGE_1 = {
  data: [
    {
      id: 'evt-1',
      event_type: 'state_transition',
      actor_id: 'user-1',
      actor_name: 'Alice',
      summary: 'Changed state to in_review',
      occurred_at: '2026-01-02T00:00:00Z',
      metadata: {},
    },
  ],
  total: 2,
  page: 1,
  page_size: 1,
};

const PAGE_2 = {
  data: [
    {
      id: 'evt-2',
      event_type: 'comment_added',
      actor_id: 'user-2',
      actor_name: 'Bob',
      summary: 'Added a comment',
      occurred_at: '2026-01-01T00:00:00Z',
      metadata: {},
    },
  ],
  total: 2,
  page: 2,
  page_size: 1,
};

describe('useTimeline', () => {
  it('returns first page of events', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', ({ request }) => {
        const url = new URL(request.url);
        const page = url.searchParams.get('page');
        return HttpResponse.json(page === '2' ? PAGE_2 : PAGE_1);
      })
    );

    const { result } = renderHook(() => useTimeline('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.events).toHaveLength(1);
    expect(result.current.hasMore).toBe(true);
  });

  it('loads more events when loadMore is called', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', ({ request }) => {
        const url = new URL(request.url);
        const page = url.searchParams.get('page');
        return HttpResponse.json(page === '2' ? PAGE_2 : PAGE_1);
      })
    );

    const { result } = renderHook(() => useTimeline('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.loadMore();
    });

    await waitFor(() => expect(result.current.events).toHaveLength(2));
    expect(result.current.hasMore).toBe(false);
  });
});
