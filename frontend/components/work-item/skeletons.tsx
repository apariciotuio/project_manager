'use client';

import { Skeleton } from '@/components/ui/skeleton';

export function VersionDiffViewerSkeleton() {
  return (
    <div className="flex flex-col gap-4 py-4" aria-hidden>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex flex-col gap-2">
          <Skeleton className="h-4 w-32" />
          <div className="flex flex-col gap-1 rounded bg-muted p-3">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
            <Skeleton className="h-3 w-3/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function CommentFeedSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-hidden>
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          data-testid="comment-skeleton-item"
          className="flex gap-3"
        >
          <Skeleton className="h-8 w-8 rounded-full shrink-0" />
          <div className="flex-1 flex flex-col gap-1.5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-12 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
