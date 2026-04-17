import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { useTaskTree } from '@/hooks/work-item/use-task-tree';

const TASKS = [
  {
    id: 'task-1',
    title: 'Design',
    status: 'done',
    order: 0,
    parent_id: null,
    dependencies: [],
    children: [
      {
        id: 'task-1-1',
        title: 'Wireframes',
        status: 'in_progress',
        order: 0,
        parent_id: 'task-1',
        dependencies: [],
        children: [],
      },
    ],
  },
];

describe('useTaskTree', () => {
  it('returns task nodes on success', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/task-tree', () =>
        HttpResponse.json({ data: TASKS })
      )
    );

    const { result } = renderHook(() => useTaskTree('wi-1'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.tasks).toHaveLength(1);
    expect(result.current.tasks.at(0)?.children).toHaveLength(1);
  });

  it('creates a task and refreshes', async () => {
    const updated = [
      ...TASKS,
      { id: 'task-2', title: 'New task', status: 'draft', order: 1, parent_id: null, dependencies: [], children: [] },
    ];

    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/task-tree', () =>
        HttpResponse.json({ data: TASKS })
      ),
      http.post('http://localhost/api/v1/work-items/wi-1/tasks', () =>
        HttpResponse.json({ data: updated[1] })
      )
    );

    const { result } = renderHook(() => useTaskTree('wi-1'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // After creating a task the hook re-fetches
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/task-tree', () =>
        HttpResponse.json({ data: updated })
      )
    );

    await result.current.createTask({ title: 'New task' });

    await waitFor(() => expect(result.current.tasks).toHaveLength(2));
  });
});
