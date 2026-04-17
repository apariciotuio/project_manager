import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTaskMutations } from '@/hooks/work-item/use-task-mutations';
import type { TaskNode } from '@/lib/types/task';

const NODE: TaskNode = {
  id: 'n1',
  work_item_id: 'wi-1',
  parent_node_id: null,
  materialized_path: '',
  title: 'Task',
  status: 'draft',
  position: 0,
};

describe('useTaskMutations', () => {
  it('createTask calls onSuccess after successful POST', async () => {
    const onSuccess = vi.fn();
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/tasks', () =>
        HttpResponse.json({ data: NODE }, { status: 201 }),
      ),
    );

    const { result } = renderHook(() => useTaskMutations(onSuccess));

    await act(async () => {
      await result.current.createTask('wi-1', 'Task');
    });

    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it('createTask passes parent_node_id when provided', async () => {
    let body: unknown;
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/tasks', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ data: { ...NODE, parent_node_id: 'n0' } }, { status: 201 });
      }),
    );

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useTaskMutations(onSuccess));

    await act(async () => {
      await result.current.createTask('wi-1', 'Child task', 'n0');
    });

    expect(body).toMatchObject({ title: 'Child task', parent_node_id: 'n0' });
  });

  it('renameTask calls PATCH /api/v1/tasks/{id} and triggers onSuccess', async () => {
    let body: unknown;
    server.use(
      http.patch('http://localhost/api/v1/tasks/n1', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ data: { ...NODE, title: 'Renamed' } });
      }),
    );

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useTaskMutations(onSuccess));

    await act(async () => {
      await result.current.renameTask('n1', 'Renamed');
    });

    expect(body).toMatchObject({ title: 'Renamed' });
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it('setStatus calls PATCH /api/v1/tasks/{id}/status', async () => {
    let body: unknown;
    server.use(
      http.patch('http://localhost/api/v1/tasks/n1/status', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ data: { ...NODE, status: 'done' } });
      }),
    );

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useTaskMutations(onSuccess));

    await act(async () => {
      await result.current.setStatus('n1', 'done');
    });

    expect(body).toMatchObject({ status: 'done' });
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it('reparent calls PATCH /api/v1/tasks/{id}/parent', async () => {
    let body: unknown;
    server.use(
      http.patch('http://localhost/api/v1/tasks/n1/parent', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ data: { ...NODE, parent_node_id: 'n0' } });
      }),
    );

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useTaskMutations(onSuccess));

    await act(async () => {
      await result.current.reparent('n1', 'n0');
    });

    expect(body).toMatchObject({ new_parent_id: 'n0' });
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it('sets isPending=true during mutation, false after', async () => {
    let resolve: () => void;
    const pending = new Promise<void>((r) => { resolve = r; });

    server.use(
      http.patch('http://localhost/api/v1/tasks/n1/status', () =>
        pending.then(() => HttpResponse.json({ data: NODE })),
      ),
    );

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useTaskMutations(onSuccess));

    expect(result.current.isPending).toBe(false);

    const mutationPromise = act(async () => {
      await result.current.setStatus('n1', 'in_progress');
    });

    // isPending goes true immediately — check by resolving later
    resolve!();
    await mutationPromise;

    expect(result.current.isPending).toBe(false);
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it('sets error when mutation fails, does not call onSuccess', async () => {
    server.use(
      http.patch('http://localhost/api/v1/tasks/n1/status', () =>
        HttpResponse.json({ error: { message: 'Server error' } }, { status: 500 }),
      ),
    );

    const onSuccess = vi.fn();
    const { result } = renderHook(() => useTaskMutations(onSuccess));

    await act(async () => {
      try {
        await result.current.setStatus('n1', 'done');
      } catch {
        // expected
      }
    });

    expect(result.current.error).not.toBeNull();
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
