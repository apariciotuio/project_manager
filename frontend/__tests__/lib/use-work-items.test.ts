import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useWorkItems } from '@/hooks/use-work-items';
import type { WorkItemResponse } from '@/lib/types/work-item';

const mockItem: WorkItemResponse = {
  id: 'wi-1',
  title: 'Test',
  type: 'task',
  state: 'draft',
  derived_state: null,
  owner_id: 'u1',
  creator_id: 'u1',
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

describe('useWorkItems', () => {
  it('returns loading=true initially', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({ data: { items: [mockItem], total: 1, page: 1, page_size: 20 } }),
      ),
    );
    const { result } = renderHook(() => useWorkItems('proj-1', {}));
    expect(result.current.isLoading).toBe(true);
  });

  it('returns items after fetch resolves', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({ data: { items: [mockItem], total: 1, page: 1, page_size: 20 } }),
      ),
    );
    const { result } = renderHook(() => useWorkItems('proj-1', {}));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0]?.id).toBe('wi-1');
    expect(result.current.total).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it('returns empty items when API returns empty list', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 20 } }),
      ),
    );
    const { result } = renderHook(() => useWorkItems('proj-1', {}));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(0);
    expect(result.current.total).toBe(0);
  });

  it('returns error on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'Not allowed' } },
          { status: 403 },
        ),
      ),
    );
    const { result } = renderHook(() => useWorkItems('proj-1', {}));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.items).toHaveLength(0);
  });

  it('does not fetch when projectId is null', () => {
    const { result } = renderHook(() => useWorkItems(null, {}));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.items).toHaveLength(0);
  });
});
