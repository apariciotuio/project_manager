import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useReassignOwner } from '@/hooks/work-item/use-reassign-owner';
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
  external_jira_key: null,
};

describe('useReassignOwner', () => {
  it('starts idle', () => {
    const { result } = renderHook(() => useReassignOwner('wi-1'));
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('PATCHes /owner with new_owner_id + reason and returns the updated item', async () => {
    let bodyReceived: unknown;
    const reassigned = { ...BASE_WORK_ITEM, owner_id: 'user-2' };
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', async ({ request }) => {
        bodyReceived = await request.json();
        return HttpResponse.json({ data: reassigned });
      }),
    );

    const { result } = renderHook(() => useReassignOwner('wi-1'));

    let returned: WorkItemResponse | null = null;
    await act(async () => {
      returned = await result.current.reassign('user-2', 'New owner on loan');
    });

    expect(returned).toEqual(reassigned);
    expect(bodyReceived).toEqual({ new_owner_id: 'user-2', reason: 'New owner on loan' });
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('omits reason from body when not provided', async () => {
    let bodyReceived: Record<string, unknown> | undefined;
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', async ({ request }) => {
        bodyReceived = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ data: BASE_WORK_ITEM });
      }),
    );

    const { result } = renderHook(() => useReassignOwner('wi-1'));

    await act(async () => {
      await result.current.reassign('user-2');
    });

    expect(bodyReceived).toEqual({ new_owner_id: 'user-2' });
    expect('reason' in (bodyReceived ?? {})).toBe(false);
  });

  it('sets error and returns null on 403 not-owner non-admin', async () => {
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'only owner/admin can reassign' } },
          { status: 403 },
        ),
      ),
    );

    const { result } = renderHook(() => useReassignOwner('wi-1'));

    let returned: WorkItemResponse | null = BASE_WORK_ITEM;
    await act(async () => {
      returned = await result.current.reassign('user-2');
    });

    expect(returned).toBeNull();
    expect(result.current.error).not.toBeNull();
  });

  it('sets error on 422 suspended target', async () => {
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', () =>
        HttpResponse.json(
          { error: { code: 'OWNER_SUSPENDED', message: 'target user is suspended' } },
          { status: 422 },
        ),
      ),
    );

    const { result } = renderHook(() => useReassignOwner('wi-1'));

    await act(async () => {
      await result.current.reassign('user-2');
    });

    expect(result.current.error).not.toBeNull();
  });
});
