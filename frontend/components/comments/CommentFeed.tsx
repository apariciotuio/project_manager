'use client';

import { MessageSquare } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/layout/empty-state';
import { CommentThread } from './CommentThread';
import { CommentInput } from './CommentInput';
import { useComments } from '@/hooks/work-item/use-comments';

export interface CommentFeedProps {
  workItemId: string;
  currentUserId: string;
}

export function CommentFeed({ workItemId, currentUserId }: CommentFeedProps) {
  const { comments, isLoading, error, addComment, deleteComment, editComment } =
    useComments(workItemId);

  async function handleSubmit(body: string, anchor?: { section_id: string; start: number; end: number; snapshot_text: string }) {
    await addComment({
      body,
      anchor_section_id: anchor?.section_id ?? null,
      anchor_start_offset: anchor?.start ?? null,
      anchor_end_offset: anchor?.end ?? null,
      anchor_snapshot_text: anchor?.snapshot_text ?? null,
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="border-b border-border pb-4">
        <CommentInput onSubmit={handleSubmit} />
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-3">
              <Skeleton className="h-8 w-8 rounded-full shrink-0" data-slot="skeleton" />
              <div className="flex-1 flex flex-col gap-1.5">
                <Skeleton className="h-4 w-24" data-slot="skeleton" />
                <Skeleton className="h-12 w-full" data-slot="skeleton" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      ) : comments.length === 0 ? (
        <EmptyState
          variant="custom"
          icon={<MessageSquare className="h-8 w-8" />}
          heading="No comments yet"
          body="Be the first to leave a comment on this item."
        />
      ) : (
        <div className="flex flex-col gap-5">
          {comments.map((comment) => (
            <CommentThread
              key={comment.id}
              comment={comment}
              currentUserId={currentUserId}
              onEdit={(id, body) => void editComment(id, body)}
              onDelete={(id) => void deleteComment(id)}
              onReply={(parentId, body) =>
                void addComment({ body, parent_comment_id: parentId })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
