'use client';

import { CommentItem } from './CommentItem';
import type { Comment } from '@/lib/types/versions';

export interface CommentThreadProps {
  comment: Comment;
  currentUserId: string;
  onEdit: (id: string, body: string) => void;
  onDelete: (id: string) => void;
  onReply: (parentId: string, body: string) => void;
}

export function CommentThread({
  comment,
  currentUserId,
  onEdit,
  onDelete,
  onReply,
}: CommentThreadProps) {
  return (
    <div className="flex flex-col gap-3">
      <CommentItem
        comment={comment}
        currentUserId={currentUserId}
        onEdit={onEdit}
        onDelete={onDelete}
        onReply={onReply}
      />

      {(comment.replies?.length ?? 0) > 0 && (
        <div className="ml-10 flex flex-col gap-3 border-l border-border pl-4">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              currentUserId={currentUserId}
              onEdit={onEdit}
              onDelete={onDelete}
              onReply={onReply}
              isReply
            />
          ))}
        </div>
      )}
    </div>
  );
}
