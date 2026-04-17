import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTransitionState } from '@/hooks/work-item/use-transition-state';
import type { WorkItemResponse } from '@/lib/types/work-item';

const BASE_WORK_ITEM: WorkItemResponse = {
  id: 'wi-1',
  title: 'Fix login bug',
  type: 'bug',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 40,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
};

describe('useTransitionState', () => {
  it('starts idle — not pending, no error', () => {
    const { result } = renderHook(() => useTransitionState('wi-1'));
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('POSTs to /transitions and returns the updated work item', async () => {
    let bodyReceived: unknown;
    const transitioned = { ...BASE_WORK_ITEM, state: 'in_clarification' as const };
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', async ({ request }) => {
        bodyReceived = await request.json();
        return HttpResponse.json({ data: transitioned });
      }),
    );

    const { result } = renderHook(() => useTransitionState('wi-1'));

    let returned: WorkItemResponse | null = null;
    await act(async () => {
      returned = await result.current.transition('in_clarification', 'Need details');
    });

    expect(returned).toEqual(transitioned);
    expect(bodyReceived).toEqual({ target_state: 'in_clarification', reason: 'Need details' });
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets isPending to true during the call and false afterwards', async () => {
    let resolve: (v: Response) => void = () => {};
    server.use(
      http.post(
        'http://localhost/api/v1/work-items/wi-1/transitions',
        () =>
          new Promise<Response>((r) => {
            resolve = r;
          }),
      ),
    );

    const { result } = renderHook(() => useTransitionState('wi-1'));

    let promise!: Promise<WorkItemResponse | null>;
    act(() => {
      promise = result.current.transition('in_clarification');
    });

    await waitFor(() => expect(result.current.isPending).toBe(true));

    resolve(HttpResponse.json({ data: BASE_WORK_ITEM }));
    await act(async () => {
      await promise;
    });

    expect(result.current.isPending).toBe(false);
  });

  it('sets error and returns null on 422 invalid transition', async () => {
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json(
          { error: { code: 'WORK_ITEM_INVALID_TRANSITION', message: 'invalid transition' } },
          { status: 422 },
        ),
      ),
    );

    const { result } = renderHook(() => useTransitionState('wi-1'));

    let returned: WorkItemResponse | null = BASE_WORK_ITEM;
    await act(async () => {
      returned = await result.current.transition('ready');
    });

    expect(returned).toBeNull();
    expect(result.current.error).not.toBeNull();
    expect(result.current.isPending).toBe(false);
  });

  it('clears previous error when a retry succeeds', async () => {
    let hits = 0;
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', () => {
        hits += 1;
        if (hits === 1) {
          return HttpResponse.json(
            { error: { code: 'WORK_ITEM_INVALID_TRANSITION', message: 'bad' } },
            { status: 422 },
          );
        }
        return HttpResponse.json({ data: { ...BASE_WORK_ITEM, state: 'in_review' } });
      }),
    );

    const { result } = renderHook(() => useTransitionState('wi-1'));

    await act(async () => {
      await result.current.transition('ready');
    });
    expect(result.current.error).not.toBeNull();

    await act(async () => {
      await result.current.transition('in_review');
    });
    expect(result.current.error).toBeNull();
  });

  it('omits reason from the body when undefined', async () => {
    let bodyReceived: Record<string, unknown> | undefined;
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', async ({ request }) => {
        bodyReceived = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ data: BASE_WORK_ITEM });
      }),
    );

    const { result } = renderHook(() => useTransitionState('wi-1'));

    await act(async () => {
      await result.current.transition('in_clarification');
    });

    expect(bodyReceived).toEqual({ target_state: 'in_clarification' });
    expect('reason' in (bodyReceived ?? {})).toBe(false);
  });
});
