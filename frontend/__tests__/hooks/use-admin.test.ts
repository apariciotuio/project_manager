import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { useAuditEvents, useHealth, useProjects, useTags } from '@/hooks/use-admin';

// ─── Audit Events ──────────────────────────────────────────────────────────────

describe('useAuditEvents', () => {
  it('returns events on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({
          data: {
            items: [
              {
                id: 'e1',
                category: 'work_item',
                action: 'create',
                actor_id: 'u1',
                actor_display: 'Ada',
                entity_type: 'work_item',
                entity_id: 'wi1',
                before_value: null,
                after_value: null,
                context: null,
                created_at: '2026-04-16T10:00:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 50,
          },
        })
      )
    );

    const { result } = renderHook(() => useAuditEvents());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.events).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/audit-events', () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'nope' } }, { status: 403 })
      )
    );

    const { result } = renderHook(() => useAuditEvents());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
  });
});

// ─── Health ────────────────────────────────────────────────────────────────────

describe('useHealth', () => {
  it('returns workspace state summary on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({
          data: {
            workspace_id: 'ws1',
            work_items_by_state: { draft: 3, in_review: 2 },
            total_active: 5,
          },
        })
      )
    );

    const { result } = renderHook(() => useHealth());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.health?.total_active).toBe(5);
    expect(result.current.health?.work_items_by_state.draft).toBe(3);
  });

  it('handles empty workspace', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/health', () =>
        HttpResponse.json({
          data: {
            workspace_id: 'ws1',
            work_items_by_state: {},
            total_active: 0,
          },
        })
      )
    );

    const { result } = renderHook(() => useHealth());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.health?.total_active).toBe(0);
  });
});

// ─── Projects ──────────────────────────────────────────────────────────────────

describe('useProjects', () => {
  it('returns projects on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/projects', () =>
        HttpResponse.json({
          data: [
            { id: 'p1', name: 'Alpha', description: null, created_at: '2026-01-01T00:00:00Z' },
          ],
        })
      )
    );

    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.projects).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it('createProject appends to list', async () => {
    server.use(
      http.get('http://localhost/api/v1/projects', () =>
        HttpResponse.json({ data: [] })
      ),
      http.post('http://localhost/api/v1/projects', () =>
        HttpResponse.json({
          data: { id: 'p2', name: 'Beta', description: 'desc', created_at: '2026-04-16T00:00:00Z' },
        })
      )
    );

    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.createProject({ name: 'Beta', description: 'desc' });
    });

    expect(result.current.projects).toHaveLength(1);
    expect(result.current.projects[0]!.name).toBe('Beta');
  });
});

// ─── Tags ──────────────────────────────────────────────────────────────────────

describe('useTags', () => {
  it('returns tags on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/tags', () =>
        HttpResponse.json({
          data: [
            { id: 'tag1', name: 'urgent', color: '#ff0000', archived: false, created_at: '2026-01-01T00:00:00Z' },
            { id: 'tag2', name: 'old', color: null, archived: true, created_at: '2025-01-01T00:00:00Z' },
          ],
        })
      )
    );

    const { result } = renderHook(() => useTags());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.tags).toHaveLength(2);
  });

  it('createTag appends to list', async () => {
    server.use(
      http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] })),
      http.post('http://localhost/api/v1/tags', () =>
        HttpResponse.json({
          data: { id: 'tag3', name: 'new', color: '#00ff00', archived: false, created_at: '2026-04-16T00:00:00Z' },
        })
      )
    );

    const { result } = renderHook(() => useTags());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.createTag({ name: 'new', color: '#00ff00' });
    });

    expect(result.current.tags).toHaveLength(1);
    expect(result.current.tags[0]!.name).toBe('new');
  });

  it('archiveTag uses DELETE (not PATCH) and filters the tag from local state', async () => {
    let deleteCalled = false;
    let patchCalled = false;
    server.use(
      http.get('http://localhost/api/v1/tags', () =>
        HttpResponse.json({
          data: [
            { id: 'tag1', name: 'urgent', color: null, archived: false, created_at: '2026-01-01T00:00:00Z' },
          ],
        })
      ),
      http.delete('http://localhost/api/v1/tags/tag1', () => {
        deleteCalled = true;
        return HttpResponse.json({});
      }),
      http.patch('http://localhost/api/v1/tags/tag1', () => {
        patchCalled = true;
        return HttpResponse.json({});
      })
    );

    const { result } = renderHook(() => useTags());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.archiveTag('tag1');
    });

    expect(deleteCalled).toBe(true);
    expect(patchCalled).toBe(false);
    // Tag is filtered out of local state on delete
    expect(result.current.tags).toHaveLength(0);
  });
});
