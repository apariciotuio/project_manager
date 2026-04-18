import Link from 'next/link';
import { cn } from '@/lib/utils';
import type { WorkItemSummary } from '@/lib/types/hierarchy';

const MAX_VISIBLE_ANCESTORS = 4;

interface BreadcrumbItemProps {
  item: WorkItemSummary;
}

function BreadcrumbItem({ item }: BreadcrumbItemProps) {
  return (
    <>
      <Link
        href={`/work-items/${item.id}`}
        className="hover:underline text-muted-foreground hover:text-foreground truncate max-w-[160px]"
      >
        {item.title}
      </Link>
      <span aria-hidden className="text-muted-foreground">
        /
      </span>
    </>
  );
}

interface BreadcrumbProps {
  ancestors: WorkItemSummary[];
  currentTitle: string;
  className?: string;
}

export function Breadcrumb({ ancestors, currentTitle, className }: BreadcrumbProps) {
  // Truncate: show first, ellipsis, last when depth > MAX_VISIBLE_ANCESTORS
  let visible: (WorkItemSummary | null)[] = ancestors;
  if (ancestors.length > MAX_VISIBLE_ANCESTORS) {
    visible = [
      ancestors[0]!,
      null, // ellipsis placeholder
      ...ancestors.slice(-(MAX_VISIBLE_ANCESTORS - 2)),
    ];
  }

  return (
    <nav
      aria-label="breadcrumb"
      className={cn('flex items-center flex-wrap gap-1 text-sm', className)}
    >
      {visible.map((item, idx) =>
        item === null ? (
          // eslint-disable-next-line react/no-array-index-key
          <span key={`ellipsis-${idx}`} className="text-muted-foreground">
            ...
          </span>
        ) : (
          <BreadcrumbItem key={item.id} item={item} />
        ),
      )}
      <span
        aria-current="page"
        className="text-foreground font-medium truncate max-w-[200px]"
      >
        {currentTitle}
      </span>
    </nav>
  );
}
