import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useWorkItemTags } from '@/hooks/work-item/use-work-item-tags';
import type { WorkItemTag } from '@/lib/types/work-item';

const TAG_BACKEND: WorkItemTag = { id: 'tag-1', name: 'backend', color: '#10b981', is_archived: false };
const TAG_FRONTEND: WorkItemTag = { id: 'tag-2', name: 'frontend', color: '#3b82f6', is_archived: false };
const TAG_ARCHIVED: WorkItemTag = { id: 'tag-3', name: 'old', color: '#cccccc', is_archived: true };

function setupHandlers(itemTags: WorkItemTag[] = [TAG_BACKEND], allTags: WorkItemTag[] = [TAG_BACKEND, TAG_FRONTEND, TAG_ARCHIVED]) {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1/tags', () =>
      HttpResponse.json({ data: itemTags })
    ),
    http.get('http://localhost/api/v1/tags', () =>
      HttpResponse.json({ data: allTags })
    )
  );
}

describe('useWorkItemTags', () => {
  it('loads attached tags and all (non-archived) workspace tags', async () => {
    setupHandlers();

    const { result } = renderHook(() => useWorkItemTags('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.tags).toHaveLength(1);
    expect(result.current.tags[0]?.name).toBe('backend');

    // allTags should exclude archived
    expect(result.current.allTags).toHaveLength(2);
    expect(result.current.allTags.map((t) => t.name)).not.toContain('old');
  });

  it('returns empty arrays when no tags attached', async () => {
    setupHandlers([], [TAG_BACKEND, TAG_FRONTEND]);

    const { result } = renderHook(() => useWorkItemTags('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.tags).toHaveLength(0);
    expect(result.current.allTags).toHaveLength(2);
  });

  it('optimistically adds a tag and confirms on success', async () => {
    setupHandlers([], [TAG_BACKEND, TAG_FRONTEND]);

    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/tags', () =>
        HttpResponse.json({ data: TAG_BACKEND })
      )
    );

    const { result } = renderHook(() => useWorkItemTags('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.addTag('tag-1');
    });

    expect(result.current.tags).toHaveLength(1);
    expect(result.current.tags[0]?.id).toBe('tag-1');
  });

  it('rolls back optimistic add on API error', async () => {
    setupHandlers([], [TAG_BACKEND]);

    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/tags', () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'Forbidden' } }, { status: 403 })
      )
    );

    const { result } = renderHook(() => useWorkItemTags('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.addTag('tag-1');
    });

    // Rolled back — tag not attached
    expect(result.current.tags).toHaveLength(0);
    expect(result.current.error).not.toBeNull();
  });

  it('optimistically removes a tag and confirms on success', async () => {
    setupHandlers([TAG_BACKEND], [TAG_BACKEND, TAG_FRONTEND]);

    server.use(
      http.delete('http://localhost/api/v1/work-items/wi-1/tags/tag-1', () =>
        new HttpResponse(null, { status: 204 })
      )
    );

    const { result } = renderHook(() => useWorkItemTags('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.tags).toHaveLength(1);

    await act(async () => {
      await result.current.removeTag('tag-1');
    });

    expect(result.current.tags).toHaveLength(0);
  });

  it('rolls back optimistic remove on API error', async () => {
    setupHandlers([TAG_BACKEND], [TAG_BACKEND, TAG_FRONTEND]);

    server.use(
      http.delete('http://localhost/api/v1/work-items/wi-1/tags/tag-1', () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'error' } }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useWorkItemTags('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.tags).toHaveLength(1);

    await act(async () => {
      await result.current.removeTag('tag-1');
    });

    // Rolled back
    expect(result.current.tags).toHaveLength(1);
    expect(result.current.error).not.toBeNull();
  });
});
