'use client';

import { useState, useCallback } from 'react';
import {
  createTask as apiCreateTask,
  renameTask as apiRenameTask,
  setTaskStatus as apiSetTaskStatus,
  reparentTask as apiReparentTask,
} from '@/lib/api/tasks';
import type { TaskStatus } from '@/lib/types/task';

export interface UseTaskMutationsResult {
  createTask: (workItemId: string, title: string, parentNodeId?: string | null) => Promise<void>;
  renameTask: (taskId: string, title: string) => Promise<void>;
  setStatus: (taskId: string, status: TaskStatus) => Promise<void>;
  reparent: (taskId: string, newParentId: string | null) => Promise<void>;
  isPending: boolean;
  error: Error | null;
}

/**
 * Provides imperative mutation helpers for task nodes.
 * Pass an `onSuccess` callback (typically `refetch` from useTaskTree)
 * that will be called after each successful mutation.
 */
export function useTaskMutations(onSuccess: () => void): UseTaskMutationsResult {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const run = useCallback(
    async (action: () => Promise<unknown>) => {
      setIsPending(true);
      setError(null);
      try {
        await action();
        onSuccess();
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        throw err;
      } finally {
        setIsPending(false);
      }
    },
    [onSuccess],
  );

  const createTask = useCallback(
    (workItemId: string, title: string, parentNodeId?: string | null) =>
      run(() => apiCreateTask(workItemId, { title, parent_node_id: parentNodeId })),
    [run],
  );

  const renameTask = useCallback(
    (taskId: string, title: string) =>
      run(() => apiRenameTask(taskId, { title })),
    [run],
  );

  const setStatus = useCallback(
    (taskId: string, status: TaskStatus) =>
      run(() => apiSetTaskStatus(taskId, { status })),
    [run],
  );

  const reparent = useCallback(
    (taskId: string, newParentId: string | null) =>
      run(() => apiReparentTask(taskId, { new_parent_id: newParentId })),
    [run],
  );

  return { createTask, renameTask, setStatus, reparent, isPending, error };
}
