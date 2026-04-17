'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api-client';
import type {
  Comment,
  CommentsResponse,
  AddCommentRequest,
} from '@/lib/types/work-item-detail';

interface UseCommentsResult {
  comments: Comment[];
  isLoading: boolean;
  error: Error | null;
  addComment: (req: AddCommentRequest) => Promise<void>;
  refetch: () => void;
}

export function useComments(workItemId: string): UseCommentsResult {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiGet<CommentsResponse>(
        `/api/v1/work-items/${workItemId}/comments`
      );
      setComments(res.data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [workItemId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const addComment = useCallback(
    async (req: AddCommentRequest) => {
      await apiPost<{ data: Comment }>(
        `/api/v1/work-items/${workItemId}/comments`,
        req
      );
      await fetch();
    },
    [workItemId, fetch]
  );

  return { comments, isLoading, error, addComment, refetch: fetch };
}
