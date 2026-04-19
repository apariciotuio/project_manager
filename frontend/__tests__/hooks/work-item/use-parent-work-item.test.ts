import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useParentWorkItem } from '@/hooks/work-item/use-parent-work-item';
import type { WorkItemResponse } from '@/lib/types/work-item';

const PARENT: WorkItemResponse = {
  id: 'wi-parent',
  title: 'Epic: Auth refactor',
  type: 'initiative',
  state: 'in_review',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 80,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

describe('useParentWorkItem', () => {
  it('returns null immediately when parentId is null', () => {
    const { result } = renderHook(() => useParentWorkItem(null));
    expect(result.current.parent).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns null immediately when parentId is undefined', () => {
    const { result } = renderHook(() => useParentWorkItem(undefined));
    expect(result.current.parent).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('fetches and returns the parent work item', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-parent', () =>
        HttpResponse.json({ data: PARENT })
      )
    );

    const { result } = renderHook(() => useParentWorkItem('wi-parent'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.parent?.id).toBe('wi-parent');
    expect(result.current.parent?.title).toBe('Epic: Auth refactor');
  });

  it('returns null and stops loading on fetch error', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-gone', () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found' } }, { status: 404 })
      )
    );

    const { result } = renderHook(() => useParentWorkItem('wi-gone'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.parent).toBeNull();
  });

  it('starts loading when parentId is provided', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-slow', async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );

    const { result } = renderHook(() => useParentWorkItem('wi-slow'));
    expect(result.current.isLoading).toBe(true);
  });
});
