import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTaskTree } from '@/hooks/work-item/use-task-tree';
import type { TaskTree } from '@/lib/types/task';

const TREE_A: TaskTree = {
  nodes: [
    {
      id: 'n1',
      work_item_id: 'wi-1',
      parent_node_id: null,
      materialized_path: '',
      title: 'Root task',
      status: 'draft',
      position: 0,
    },
    {
      id: 'n2',
      work_item_id: 'wi-1',
      parent_node_id: 'n1',
      materialized_path: 'n1',
      title: 'Child task',
      status: 'in_progress',
      position: 0,
    },
  ],
  edges: [
    { id: 'e1', from_node_id: 'n1', to_node_id: 'n2', kind: 'blocks' },
  ],
};

const TREE_EMPTY: TaskTree = { nodes: [], edges: [] };

describe('useTaskTree', () => {
  it('starts loading and resolves tree on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/tasks', () =>
        HttpResponse.json({ data: TREE_A }),
      ),
    );

    const { result } = renderHook(() => useTaskTree('wi-1'));

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeNull();
    expect(result.current.tree.nodes).toHaveLength(2);
    expect(result.current.tree.edges).toHaveLength(1);
  });

  it('returns empty tree when endpoint returns no nodes', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-2/tasks', () =>
        HttpResponse.json({ data: TREE_EMPTY }),
      ),
    );

    const { result } = renderHook(() => useTaskTree('wi-2'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.tree.nodes).toHaveLength(0);
    expect(result.current.tree.edges).toHaveLength(0);
  });

  it('surfaces error when request fails', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-fail/tasks', () =>
        HttpResponse.json({ error: { message: 'Not found' } }, { status: 404 }),
      ),
    );

    const { result } = renderHook(() => useTaskTree('wi-fail'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).not.toBeNull();
    expect(result.current.tree.nodes).toHaveLength(0);
  });

  it('refetch re-fetches tree from server', async () => {
    let callCount = 0;
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/tasks', () => {
        callCount += 1;
        const tree: TaskTree =
          callCount === 1
            ? TREE_EMPTY
            : TREE_A;
        return HttpResponse.json({ data: tree });
      }),
    );

    const { result } = renderHook(() => useTaskTree('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.tree.nodes).toHaveLength(0);

    act(() => { result.current.refetch(); });
    await waitFor(() => expect(result.current.tree.nodes).toHaveLength(2));
  });

  it('exposes nodes with correct shape', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/tasks', () =>
        HttpResponse.json({ data: TREE_A }),
      ),
    );

    const { result } = renderHook(() => useTaskTree('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const node = result.current.tree.nodes[0];
    expect(node).toMatchObject({
      id: 'n1',
      work_item_id: 'wi-1',
      parent_node_id: null,
      title: 'Root task',
      status: 'draft',
      position: 0,
    });
  });
});
