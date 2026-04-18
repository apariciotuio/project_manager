'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { useComments } from '@/hooks/work-item/use-comments';
import type { Comment, CreateCommentRequest } from '@/lib/types/versions';

export interface CommentsContextValue {
  workItemId: string;
  comments: Comment[];
  isLoading: boolean;
  error: Error | null;
  addComment: (req: CreateCommentRequest) => Promise<void>;
  deleteComment: (commentId: string) => Promise<void>;
  refetch: () => Promise<void>;
}

const CommentsContext = createContext<CommentsContextValue | null>(null);

interface CommentsProviderProps {
  workItemId: string;
  children: ReactNode;
}

export function CommentsProvider({ workItemId, children }: CommentsProviderProps) {
  const state = useComments(workItemId);
  const value: CommentsContextValue = {
    workItemId,
    comments: state.comments,
    isLoading: state.isLoading,
    error: state.error,
    addComment: state.addComment,
    deleteComment: state.deleteComment,
    refetch: state.refetch,
  };
  return <CommentsContext.Provider value={value}>{children}</CommentsContext.Provider>;
}

export function useCommentsContext(): CommentsContextValue | null {
  return useContext(CommentsContext);
}
