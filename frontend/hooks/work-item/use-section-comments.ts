'use client';

import { useState, useEffect, useCallback } from 'react';
import { listSectionComments } from '@/lib/api/comments';
import type { Comment } from '@/lib/types/versions';

interface UseSectionCommentsResult {
  comments: Comment[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useSectionComments(
  workItemId: string,
  sectionId: string,
): UseSectionCommentsResult {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listSectionComments(workItemId, sectionId);
      setComments(data);
    } catch (err) {
      setComments([]);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId, sectionId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { comments, isLoading, error, refetch: fetch };
}
