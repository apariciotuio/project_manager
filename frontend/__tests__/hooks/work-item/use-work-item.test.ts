import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useWorkItem } from '@/hooks/work-item/use-work-item';
import type { WorkItemResponse } from '@/lib/types/work-item';

const WORK_ITEM: WorkItemResponse = {
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
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
};

describe('useWorkItem', () => {
  it('returns data on successful fetch', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1', () =>
        HttpResponse.json({ data: WORK_ITEM })
      )
    );

    const { result } = renderHook(() => useWorkItem('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.workItem?.id).toBe('wi-1');
    expect(result.current.error).toBeNull();
  });

  it('returns error on 404', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-999', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useWorkItem('wi-999'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.workItem).toBeNull();
    expect(result.current.error).not.toBeNull();
  });

  it('starts in loading state', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1', async () => {
        await new Promise(() => {}); // never resolves
        return HttpResponse.json({});
      })
    );

    const { result } = renderHook(() => useWorkItem('wi-1'));
    expect(result.current.isLoading).toBe(true);
  });
});
