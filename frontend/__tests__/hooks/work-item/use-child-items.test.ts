import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useChildItems } from '@/hooks/work-item/use-child-items';
import type { WorkItemResponse } from '@/lib/types/work-item';

const makeChild = (id: string, title: string): WorkItemResponse => ({
  id,
  title,
  type: 'story',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 0,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: 'wi-parent',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
});

const PAGED_EMPTY = { items: [], total: 0, page: 1, page_size: 50 };

describe('useChildItems', () => {
  it('returns empty list when no children', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({ data: PAGED_EMPTY })
      )
    );

    const { result } = renderHook(() => useChildItems('wi-parent'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.children).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });

  it('returns children when they exist', async () => {
    const children = [
      makeChild('wi-child-1', 'Child story 1'),
      makeChild('wi-child-2', 'Child story 2'),
    ];

    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({ data: { items: children, total: 2, page: 1, page_size: 50 } })
      )
    );

    const { result } = renderHook(() => useChildItems('wi-parent'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.children).toHaveLength(2);
    expect(result.current.children[0]?.title).toBe('Child story 1');
    expect(result.current.children[1]?.title).toBe('Child story 2');
  });

  it('starts in loading state', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );

    const { result } = renderHook(() => useChildItems('wi-parent'));
    expect(result.current.isLoading).toBe(true);
  });

  it('sets error state on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'boom' } }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useChildItems('wi-parent'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).not.toBeNull();
    expect(result.current.children).toHaveLength(0);
  });
});
