'use client';

import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api-client';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface UseParentWorkItemResult {
  parent: WorkItemResponse | null;
  isLoading: boolean;
}

export function useParentWorkItem(
  parentId: string | null | undefined
): UseParentWorkItemResult {
  const [parent, setParent] = useState<WorkItemResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!parentId) {
      setParent(null);
      return;
    }

    setIsLoading(true);
    apiGet<{ data: WorkItemResponse }>(`/api/v1/work-items/${parentId}`)
      .then((res) => setParent(res.data))
      .catch(() => setParent(null))
      .finally(() => setIsLoading(false));
  }, [parentId]);

  return { parent, isLoading };
}
