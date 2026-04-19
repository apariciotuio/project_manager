import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useForceReady } from '@/hooks/work-item/use-force-ready';
import type { WorkItemResponse } from '@/lib/types/work-item';

const BASE_WORK_ITEM: WorkItemResponse = {
  id: 'wi-1',
  title: 'Fix login bug',
  type: 'bug',
  state: 'in_review',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 85,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

describe('useForceReady', () => {
  it('starts idle', () => {
    const { result } = renderHook(() => useForceReady('wi-1'));
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('POSTs with justification + confirmed=true and returns the overridden item', async () => {
    let bodyReceived: unknown;
    const overridden = {
      ...BASE_WORK_ITEM,
      state: 'ready' as const,
      has_override: true,
      override_justification: 'Ship for demo',
    };
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/force-ready', async ({ request }) => {
        bodyReceived = await request.json();
        return HttpResponse.json({ data: overridden });
      }),
    );

    const { result } = renderHook(() => useForceReady('wi-1'));

    let returned: WorkItemResponse | null = null;
    await act(async () => {
      returned = await result.current.forceReady('Ship for demo');
    });

    expect(returned).toEqual(overridden);
    expect(bodyReceived).toEqual({ justification: 'Ship for demo', confirmed: true });
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets error and returns null on 422 CONFIRMATION_REQUIRED', async () => {
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/force-ready', () =>
        HttpResponse.json(
          { error: { code: 'CONFIRMATION_REQUIRED', message: 'confirmed must be true' } },
          { status: 422 },
        ),
      ),
    );

    const { result } = renderHook(() => useForceReady('wi-1'));

    let returned: WorkItemResponse | null = BASE_WORK_ITEM;
    await act(async () => {
      returned = await result.current.forceReady('Reason');
    });

    expect(returned).toBeNull();
    expect(result.current.error).not.toBeNull();
  });

  it('sets error and returns null on 403 not-owner', async () => {
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/force-ready', () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'not owner' } },
          { status: 403 },
        ),
      ),
    );

    const { result } = renderHook(() => useForceReady('wi-1'));

    let returned: WorkItemResponse | null = BASE_WORK_ITEM;
    await act(async () => {
      returned = await result.current.forceReady('Reason');
    });

    expect(returned).toBeNull();
    expect(result.current.error).not.toBeNull();
  });
});
