import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTimeline } from '@/hooks/work-item/use-timeline';

// Fixtures use the BE contract: actor_display_name, payload, has_more

const EVT_1 = {
  id: 'evt-1',
  work_item_id: 'wi-1',
  workspace_id: 'ws-1',
  event_type: 'state_transition',
  actor_type: 'human',
  actor_id: 'user-1',
  actor_display_name: 'Alice',
  summary: 'Changed state to in_review',
  payload: { from_state: 'draft', to_state: 'in_review' },
  occurred_at: '2026-01-02T00:00:00Z',
  source_id: null,
  source_table: null,
};

const EVT_2 = {
  id: 'evt-2',
  work_item_id: 'wi-1',
  workspace_id: 'ws-1',
  event_type: 'comment_added',
  actor_type: 'human',
  actor_id: 'user-2',
  actor_display_name: 'Bob',
  summary: 'Added a comment',
  payload: { comment_id: 'c-1' },
  occurred_at: '2026-01-01T00:00:00Z',
  source_id: null,
  source_table: null,
};

const PAGE_1 = {
  data: {
    events: [EVT_1],
    has_more: true,
    next_cursor: 'cursor-2',
  },
};

const PAGE_2 = {
  data: {
    events: [EVT_2],
    has_more: false,
    next_cursor: null,
  },
};

function makeHandler() {
  return http.get('http://localhost/api/v1/work-items/wi-1/timeline', ({ request }) => {
    const url = new URL(request.url);
    const cursor = url.searchParams.get('cursor');
    return HttpResponse.json(cursor === 'cursor-2' ? PAGE_2 : PAGE_1);
  });
}

describe('useTimeline', () => {
  it('returns first page of events', async () => {
    server.use(makeHandler());

    const { result } = renderHook(() => useTimeline('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]?.actor_display_name).toBe('Alice');
    expect(result.current.events[0]?.payload).toEqual({ from_state: 'draft', to_state: 'in_review' });
    expect(result.current.hasMore).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('loads more events when loadMore is called and appends to list', async () => {
    server.use(makeHandler());

    const { result } = renderHook(() => useTimeline('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.loadMore();
    });

    await waitFor(() => expect(result.current.events).toHaveLength(2));

    expect(result.current.events[0]?.id).toBe('evt-1');
    expect(result.current.events[1]?.id).toBe('evt-2');
    expect(result.current.hasMore).toBe(false);
  });

  it('sets error when request fails', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
        HttpResponse.json({ error: 'Internal Server Error' }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useTimeline('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).not.toBeNull();
    expect(result.current.events).toHaveLength(0);
  });

  it('hasMore is false when BE returns has_more=false even if next_cursor is null', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
        HttpResponse.json({ data: { events: [EVT_1], has_more: false, next_cursor: null } })
      )
    );

    const { result } = renderHook(() => useTimeline('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.hasMore).toBe(false);
  });

  it('forwards eventTypes, actorTypes and dateRange as query params', async () => {
    let lastUrl: URL | null = null;
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', ({ request }) => {
        lastUrl = new URL(request.url);
        return HttpResponse.json(PAGE_1);
      })
    );

    const filters = {
      eventTypes: ['state_transition' as const, 'comment_added' as const],
      actorTypes: ['ai_suggestion' as const],
      dateRange: { from: '2026-04-01', to: '2026-04-15' },
    };

    const { result } = renderHook(() => useTimeline('wi-1', filters));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(lastUrl).not.toBeNull();
    const url = lastUrl as unknown as URL;
    expect(url.searchParams.getAll('event_types')).toEqual([
      'state_transition',
      'comment_added',
    ]);
    expect(url.searchParams.getAll('actor_types')).toEqual(['ai_suggestion']);
    expect(url.searchParams.get('from_date')).toBe('2026-04-01');
    expect(url.searchParams.get('to_date')).toBe('2026-04-15');
  });

  it('changing filters resets events and refetches from cursor=null', async () => {
    let requestCount = 0;
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/timeline', ({ request }) => {
        requestCount += 1;
        const url = new URL(request.url);
        const evtTypes = url.searchParams.getAll('event_types');
        return HttpResponse.json({
          data: {
            events:
              evtTypes.length === 0
                ? [EVT_1, EVT_2]
                : [{ ...EVT_1, id: 'evt-filtered' }],
            has_more: false,
            next_cursor: null,
          },
        });
      })
    );

    const { result, rerender } = renderHook(
      ({ filters }: { filters?: Parameters<typeof useTimeline>[1] }) =>
        useTimeline('wi-1', filters),
      { initialProps: { filters: undefined as Parameters<typeof useTimeline>[1] | undefined } },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.events).toHaveLength(2);

    rerender({
      filters: {
        eventTypes: ['state_transition'],
        actorTypes: [],
        dateRange: { from: null, to: null },
      },
    });

    await waitFor(() => expect(result.current.events).toHaveLength(1));
    expect(result.current.events[0]?.id).toBe('evt-filtered');
    expect(requestCount).toBe(2);
  });
});
