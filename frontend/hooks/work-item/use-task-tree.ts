'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api-client';
import type {
  TaskNode,
  TaskTreeResponse,
  CreateTaskRequest,
} from '@/lib/types/work-item-detail';

interface UseTaskTreeResult {
  tasks: TaskNode[];
  isLoading: boolean;
  error: Error | null;
  createTask: (req: CreateTaskRequest) => Promise<void>;
  refetch: () => void;
}

export function useTaskTree(workItemId: string): UseTaskTreeResult {
  const [tasks, setTasks] = useState<TaskNode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<TaskTreeResponse>(
        `/api/v1/work-items/${workItemId}/task-tree`
      );
      setTasks(res.data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const createTask = useCallback(
    async (req: CreateTaskRequest) => {
      await apiPost<{ data: TaskNode }>(
        `/api/v1/work-items/${workItemId}/tasks`,
        req
      );
      await fetch();
    },
    [workItemId, fetch]
  );

  return { tasks, isLoading, error, createTask, refetch: fetch };
}
