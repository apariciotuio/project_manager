/**
 * EP-01 Phase 2 — API client tests (RED first, then GREEN).
 * MSW intercepts all requests at http://localhost (set by NEXT_PUBLIC_API_BASE_URL in setup.ts).
 */
import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { ApiError } from '@/lib/types/auth';
import type { WorkItemResponse, StateTransitionRecord, OwnershipRecord } from '@/lib/types/work-item';
import {
  createWorkItem,
  getWorkItem,
  listWorkItems,
  updateWorkItem,
  deleteWorkItem,
  transitionState,
  forceReady,
  reassignOwner,
  getTransitions,
  getOwnershipHistory,
} from '@/lib/api/work-items';

const BASE = 'http://localhost';

const mockWorkItem: WorkItemResponse = {
  id: '00000000-0000-0000-0000-000000000001',
  title: 'Test item',
  type: 'bug',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 10,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  created_at: '2026-04-15T00:00:00Z',
  updated_at: '2026-04-15T00:00:00Z',
  deleted_at: null,
};

// ─── createWorkItem ───────────────────────────────────────────────────────────

describe('createWorkItem', () => {
  it('returns typed WorkItemResponse on 201', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items`, () =>
        HttpResponse.json({ data: mockWorkItem }, { status: 201 }),
      ),
    );
    const result = await createWorkItem({
      title: 'Test',
      type: 'bug',
      project_id: 'proj-1',
    });
    expect(result.state).toBe('draft');
    expect(result.id).toBe(mockWorkItem.id);
  });

  it('throws ApiError with code on 422', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items`, () =>
        HttpResponse.json(
          { error: { code: 'VALIDATION_ERROR', message: 'Invalid', details: { field: 'title' } } },
          { status: 422 },
        ),
      ),
    );
    const err = await createWorkItem({ title: 'ab', type: 'bug', project_id: 'p' }).catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe('VALIDATION_ERROR');
    expect((err as ApiError).details).toMatchObject({ field: 'title' });
  });
});

// ─── getWorkItem ──────────────────────────────────────────────────────────────

describe('getWorkItem', () => {
  it('returns WorkItemResponse on 200', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/:id`, () =>
        HttpResponse.json({ data: mockWorkItem }),
      ),
    );
    const result = await getWorkItem(mockWorkItem.id);
    expect(result.id).toBe(mockWorkItem.id);
    expect(result.type).toBe('bug');
  });

  it('throws ApiError with WORK_ITEM_NOT_FOUND code on 404', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/:id`, () =>
        HttpResponse.json(
          { error: { code: 'WORK_ITEM_NOT_FOUND', message: 'Not found' } },
          { status: 404 },
        ),
      ),
    );
    const err = await getWorkItem('nonexistent').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe('WORK_ITEM_NOT_FOUND');
    expect((err as ApiError).status).toBe(404);
  });

  it('does NOT return null on 404 — throws instead', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/:id`, () =>
        HttpResponse.json(
          { error: { code: 'WORK_ITEM_NOT_FOUND', message: 'Not found' } },
          { status: 404 },
        ),
      ),
    );
    await expect(getWorkItem('nonexistent')).rejects.toBeInstanceOf(ApiError);
  });
});

// ─── listWorkItems ────────────────────────────────────────────────────────────

describe('listWorkItems', () => {
  it('returns paged response on 200', async () => {
    server.use(
      http.get(`${BASE}/api/v1/projects/:projectId/work-items`, () =>
        HttpResponse.json({
          data: { items: [mockWorkItem], total: 1, page: 1, page_size: 20 },
        }),
      ),
    );
    const result = await listWorkItems('proj-1', {});
    expect(result.items).toHaveLength(1);
    expect(result.total).toBe(1);
    expect(result.page).toBe(1);
  });

  it('passes filter params in query string', async () => {
    let capturedUrl: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/projects/:projectId/work-items`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          data: { items: [], total: 0, page: 1, page_size: 20 },
        });
      }),
    );
    await listWorkItems('proj-1', { state: 'draft', page: 2 });
    expect(capturedUrl).toContain('state=draft');
    expect(capturedUrl).toContain('page=2');
  });
});

// ─── updateWorkItem ───────────────────────────────────────────────────────────

describe('updateWorkItem', () => {
  it('returns updated WorkItemResponse on 200', async () => {
    const updated = { ...mockWorkItem, title: 'Updated title' };
    server.use(
      http.patch(`${BASE}/api/v1/work-items/:id`, () =>
        HttpResponse.json({ data: updated }),
      ),
    );
    const result = await updateWorkItem(mockWorkItem.id, { title: 'Updated title' });
    expect(result.title).toBe('Updated title');
  });
});

// ─── deleteWorkItem ───────────────────────────────────────────────────────────

describe('deleteWorkItem', () => {
  it('resolves void on 204', async () => {
    server.use(
      http.delete(`${BASE}/api/v1/work-items/:id`, () => new HttpResponse(null, { status: 204 })),
    );
    await expect(deleteWorkItem(mockWorkItem.id)).resolves.toBeUndefined();
  });

  it('throws ApiError on 403 (not draft)', async () => {
    server.use(
      http.delete(`${BASE}/api/v1/work-items/:id`, () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'Only draft items can be deleted' } },
          { status: 403 },
        ),
      ),
    );
    const err = await deleteWorkItem(mockWorkItem.id).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(403);
  });
});

// ─── transitionState ─────────────────────────────────────────────────────────

describe('transitionState', () => {
  it('returns updated WorkItemResponse on success', async () => {
    const transitioned = { ...mockWorkItem, state: 'in_clarification' as const };
    server.use(
      http.post(`${BASE}/api/v1/work-items/:id/transitions`, () =>
        HttpResponse.json({ data: transitioned }),
      ),
    );
    const result = await transitionState(mockWorkItem.id, { target_state: 'in_clarification' });
    expect(result.state).toBe('in_clarification');
  });

  it('throws ApiError with from_state and to_state on 422', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/:id/transitions`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'INVALID_TRANSITION',
              message: 'Invalid',
              details: { from_state: 'exported', to_state: 'draft' },
            },
          },
          { status: 422 },
        ),
      ),
    );
    const err = await transitionState(mockWorkItem.id, { target_state: 'draft' }).catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe('INVALID_TRANSITION');
    expect((err as ApiError).details).toMatchObject({ from_state: 'exported', to_state: 'draft' });
  });
});

// ─── forceReady ───────────────────────────────────────────────────────────────

describe('forceReady', () => {
  it('returns updated WorkItemResponse on success', async () => {
    const ready = { ...mockWorkItem, state: 'ready' as const, has_override: true };
    server.use(
      http.post(`${BASE}/api/v1/work-items/:id/force-ready`, () =>
        HttpResponse.json({ data: ready }),
      ),
    );
    const result = await forceReady(mockWorkItem.id, {
      justification: 'Shipping this week',
      confirmed: true,
    });
    expect(result.state).toBe('ready');
    expect(result.has_override).toBe(true);
  });

  it('throws ApiError with NOT_OWNER code on 403', async () => {
    server.use(
      http.post(`${BASE}/api/v1/work-items/:id/force-ready`, () =>
        HttpResponse.json(
          { error: { code: 'NOT_OWNER', message: 'Not the owner' } },
          { status: 403 },
        ),
      ),
    );
    const err = await forceReady(mockWorkItem.id, {
      justification: 'test',
      confirmed: true,
    }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe('NOT_OWNER');
    expect((err as ApiError).status).toBe(403);
  });
});

// ─── reassignOwner ────────────────────────────────────────────────────────────

describe('reassignOwner', () => {
  it('returns updated WorkItemResponse with new owner on 200', async () => {
    const reassigned = { ...mockWorkItem, owner_id: 'user-2' };
    server.use(
      http.patch(`${BASE}/api/v1/work-items/:id/owner`, () =>
        HttpResponse.json({ data: reassigned }),
      ),
    );
    const result = await reassignOwner(mockWorkItem.id, { new_owner_id: 'user-2' });
    expect(result.owner_id).toBe('user-2');
  });
});

// ─── getTransitions ───────────────────────────────────────────────────────────

describe('getTransitions', () => {
  it('returns array of StateTransitionRecord on 200', async () => {
    const records: StateTransitionRecord[] = [
      {
        id: 'tr-1',
        work_item_id: mockWorkItem.id,
        from_state: 'draft',
        to_state: 'in_clarification',
        actor_id: 'user-1',
        triggered_at: '2026-04-15T00:00:00Z',
        transition_reason: null,
        is_override: false,
        override_justification: null,
      },
    ];
    server.use(
      http.get(`${BASE}/api/v1/work-items/:id/transitions`, () =>
        HttpResponse.json({ data: records }),
      ),
    );
    const result = await getTransitions(mockWorkItem.id);
    expect(result).toHaveLength(1);
    expect(result[0]?.from_state).toBe('draft');
    expect(result[0]?.to_state).toBe('in_clarification');
  });
});

// ─── getOwnershipHistory ──────────────────────────────────────────────────────

describe('getOwnershipHistory', () => {
  it('returns array of OwnershipRecord on 200', async () => {
    const records: OwnershipRecord[] = [
      {
        id: 'oh-1',
        work_item_id: mockWorkItem.id,
        previous_owner_id: 'user-1',
        new_owner_id: 'user-2',
        changed_by: 'user-1',
        changed_at: '2026-04-15T00:00:00Z',
        reason: null,
      },
    ];
    server.use(
      http.get(`${BASE}/api/v1/work-items/:id/ownership-history`, () =>
        HttpResponse.json({ data: records }),
      ),
    );
    const result = await getOwnershipHistory(mockWorkItem.id);
    expect(result).toHaveLength(1);
    expect(result[0]?.new_owner_id).toBe('user-2');
  });
});
