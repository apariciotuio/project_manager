'use client';

import { CommentFeed } from '@/components/comments/CommentFeed';
import { useAuth } from '@/app/providers/auth-provider';

interface CommentsTabProps {
  workItemId: string;
}

export function CommentsTab({ workItemId }: CommentsTabProps) {
  const { user } = useAuth();
  return (
    <CommentFeed workItemId={workItemId} currentUserId={user?.id ?? ''} />
  );
}
