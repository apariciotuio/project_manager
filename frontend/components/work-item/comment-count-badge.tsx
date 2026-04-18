'use client';

import { cn } from '@/lib/utils';
import { useCommentsContext } from './comments-context';
import type { Comment } from '@/lib/types/versions';

function countLive(comments: readonly Comment[]): number {
  let count = 0;
  for (const c of comments) {
    if (!c.deleted_at) count += 1;
    for (const r of c.replies ?? []) {
      if (!r.deleted_at) count += 1;
    }
  }
  return count;
}

interface CommentCountBadgeProps {
  className?: string;
}

export function CommentCountBadge({ className }: CommentCountBadgeProps) {
  const ctx = useCommentsContext();
  if (ctx === null) return null;
  const count = countLive(ctx.comments);
  if (count === 0) return null;
  return (
    <span
      aria-label={`${count} comentarios`}
      data-testid="comment-count-badge"
      className={cn(
        'inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground text-[10px] min-w-[1.25rem] h-5 px-1.5 font-medium',
        className,
      )}
    >
      {count}
    </span>
  );
}
