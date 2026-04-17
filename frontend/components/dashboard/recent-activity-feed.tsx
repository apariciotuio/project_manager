import Link from 'next/link';
import { useTranslations } from 'next-intl';
import type { DashboardActivityItem } from '@/lib/types/work-item';

interface RecentActivityFeedProps {
  items: DashboardActivityItem[];
  slug: string;
}

/**
 * EP-09 — Recent activity feed for workspace dashboard.
 */
export function RecentActivityFeed({ items, slug }: RecentActivityFeedProps) {
  const tDash = useTranslations('workspace.dashboard');

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <h3 className="text-body font-semibold text-foreground">
        {tDash('recentActivity.title')}
      </h3>

      {items.length === 0 ? (
        <p className="text-body-sm text-muted-foreground">{tDash('recentActivity.empty')}</p>
      ) : (
        <ul
          role="list"
          aria-label={tDash('recentActivity.title')}
          data-testid="recent-activity-list"
          className="divide-y divide-border"
        >
          {items.map((item) => (
            <li key={`${item.work_item_id}-${item.occurred_at}`} className="py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <Link
                    href={`/workspace/${slug}/items/${item.work_item_id}`}
                    aria-label={tDash('recentActivity.viewItem')}
                    className="text-body-sm font-medium text-foreground hover:text-primary truncate block"
                  >
                    {item.title}
                  </Link>
                  <p className="text-body-sm text-muted-foreground">
                    {item.event_type}
                    {item.actor_name && ` · ${item.actor_name}`}
                  </p>
                </div>
                <time
                  dateTime={item.occurred_at}
                  className="shrink-0 text-body-sm text-muted-foreground tabular-nums"
                >
                  {new Date(item.occurred_at).toLocaleDateString()}
                </time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
