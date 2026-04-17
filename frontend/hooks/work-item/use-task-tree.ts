'use client';

import { useState, useEffect, useCallback } from 'react';
import { getTaskTree } from '@/lib/api/tasks';
import type { TaskTree } from '@/lib/types/task';

export interface UseTaskTreeResult {
  tree: TaskTree;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

const EMPTY_TREE: TaskTree = { nodes: [], edges: [] };

export function useTaskTree(workItemId: string): UseTaskTreeResult {
  const [tree, setTree] = useState<TaskTree>(EMPTY_TREE);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getTaskTree(workItemId);
      setTree(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { tree, isLoading, error, refetch };
}
