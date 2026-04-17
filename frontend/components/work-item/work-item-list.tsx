import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { WorkItemCard } from '@/components/work-item/work-item-card';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface WorkItemListProps {
  items: WorkItemResponse[];
  slug: string;
  isLoading?: boolean;
  error?: Error | null;
  /** Rendered when items is empty and not loading/error. */
  emptyState?: React.ReactNode;
}

export function WorkItemList({ items, slug, isLoading, error, emptyState }: WorkItemListProps) {
  const tItems = useTranslations('workspace.items');

  if (isLoading) {
    return (
      <div data-testid="work-items-skeleton" className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="text-body-sm text-destructive">
        {tItems('errorBanner')}: {error.message}
      </div>
    );
  }

  if (items.length === 0) {
    return emptyState ? <>{emptyState}</> : null;
  }

  return (
    <ul
      role="list"
      aria-label={tItems('listAria')}
      className="overflow-hidden rounded-lg border border-border divide-y divide-border"
    >
      {items.map((item) => (
        <li key={item.id}>
          <WorkItemCard workItem={item} slug={slug} />
        </li>
      ))}
    </ul>
  );
}
