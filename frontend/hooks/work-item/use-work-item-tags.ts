'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiDelete } from '@/lib/api-client';
import type { WorkItemTag } from '@/lib/types/work-item';

interface UseWorkItemTagsResult {
  tags: WorkItemTag[];
  allTags: WorkItemTag[];
  isLoading: boolean;
  error: Error | null;
  addTag: (tagId: string) => Promise<void>;
  removeTag: (tagId: string) => Promise<void>;
}

export function useWorkItemTags(workItemId: string): UseWorkItemTagsResult {
  const [tags, setTags] = useState<WorkItemTag[]>([]);
  const [allTags, setAllTags] = useState<WorkItemTag[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTags = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [itemTagsRes, allTagsRes] = await Promise.all([
        apiGet<{ data: WorkItemTag[] }>(`/api/v1/work-items/${workItemId}/tags`),
        apiGet<{ data: WorkItemTag[] }>('/api/v1/tags'),
      ]);
      setTags(itemTagsRes.data);
      setAllTags(allTagsRes.data.filter((t) => !t.is_archived));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetchTags();
  }, [fetchTags]);

  const addTag = useCallback(
    async (tagId: string) => {
      const tagToAdd = allTags.find((t) => t.id === tagId);
      if (!tagToAdd) return;

      // Optimistic update
      setTags((prev) => [...prev, tagToAdd]);

      try {
        await apiPost<{ data: WorkItemTag }>(
          `/api/v1/work-items/${workItemId}/tags`,
          { tag_id: tagId }
        );
      } catch (err) {
        // Rollback
        setTags((prev) => prev.filter((t) => t.id !== tagId));
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    },
    [workItemId, allTags]
  );

  const removeTag = useCallback(
    async (tagId: string) => {
      const snapshot = tags;

      // Optimistic update
      setTags((prev) => prev.filter((t) => t.id !== tagId));

      try {
        await apiDelete<void>(`/api/v1/work-items/${workItemId}/tags/${tagId}`);
      } catch (err) {
        // Rollback
        setTags(snapshot);
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    },
    [workItemId, tags]
  );

  return { tags, allTags, isLoading, error, addTag, removeTag };
}
