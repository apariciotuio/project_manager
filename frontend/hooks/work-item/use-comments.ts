'use client';

import { useState, useEffect, useCallback } from 'react';
import { listComments, deleteComment as apiDeleteComment, updateComment as apiUpdateComment } from '@/lib/api/comments';
import { createComment } from '@/lib/api/versions';
import type { Comment, CreateCommentRequest } from '@/lib/types/versions';

interface UseCommentsResult {
  comments: Comment[];
  isLoading: boolean;
  error: Error | null;
  addComment: (req: CreateCommentRequest) => Promise<void>;
  deleteComment: (commentId: string) => Promise<void>;
  editComment: (commentId: string, body: string) => Promise<void>;
  refetch: () => Promise<void>;
}

export function useComments(workItemId: string): UseCommentsResult {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listComments(workItemId);
      setComments(data);
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
    async (req: CreateCommentRequest) => {
      // Optimistic: append a placeholder immediately
      const optimisticId = `optimistic-${Date.now()}`;
      const optimistic: Comment = {
        id: optimisticId,
        work_item_id: workItemId,
        parent_comment_id: req.parent_comment_id ?? null,
        body: req.body,
        actor_type: 'human',
        actor_id: null,
        anchor_section_id: req.anchor_section_id ?? null,
        anchor_start_offset: req.anchor_start_offset ?? null,
        anchor_end_offset: req.anchor_end_offset ?? null,
        anchor_snapshot_text: req.anchor_snapshot_text ?? null,
        anchor_status: 'active',
        is_edited: false,
        deleted_at: null,
        created_at: new Date().toISOString(),
        replies: [],
      };

      setComments((prev) => [...prev, optimistic]);
      setError(null);

      try {
        const created = await createComment(workItemId, req);
        // Replace optimistic placeholder with real item, then sync from server
        setComments((prev) =>
          prev.map((c) => (c.id === optimisticId ? created : c)),
        );
        // Sync authoritative list in background
        listComments(workItemId)
          .then((data) => setComments(data))
          .catch(() => {/* non-critical */});
      } catch (err) {
        // Rollback
        setComments((prev) => prev.filter((c) => c.id !== optimisticId));
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        throw e;
      }
    },
    [workItemId],
  );

  const deleteComment = useCallback(
    async (commentId: string) => {
      // Optimistic: remove immediately
      setComments((prev) => prev.filter((c) => c.id !== commentId));
      setError(null);

      try {
        await apiDeleteComment(workItemId, commentId);
      } catch (err) {
        // Rollback: re-fetch authoritative list
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        try {
          const data = await listComments(workItemId);
          setComments(data);
        } catch {
          // fetch failed too — at least expose the original error
        }
        throw e;
      }
    },
    [workItemId],
  );

  const editComment = useCallback(
    async (commentId: string, body: string) => {
      // Optimistic: update body immediately
      setComments((prev) =>
        prev.map((c) =>
          c.id === commentId ? { ...c, body, is_edited: true } : c,
        ),
      );
      setError(null);

      try {
        const updated = await apiUpdateComment(workItemId, commentId, body);
        setComments((prev) =>
          prev.map((c) => (c.id === commentId ? updated : c)),
        );
      } catch (err) {
        // Rollback
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        try {
          const data = await listComments(workItemId);
          setComments(data);
        } catch {
          // fetch failed too
        }
        throw e;
      }
    },
    [workItemId],
  );

  return { comments, isLoading, error, addComment, deleteComment, editComment, refetch: fetch };
}
