'use client';

import { useTranslations } from 'next-intl';
import { RelativeTime } from '@/components/domain/relative-time';
import { Skeleton } from '@/components/ui/skeleton';
import { useOwnershipHistory } from '@/hooks/work-item/use-ownership-history';

export interface OwnershipHistoryProps {
  workItemId: string;
}

export function OwnershipHistory({ workItemId }: OwnershipHistoryProps) {
  const t = useTranslations('workspace.itemDetail.audit.ownership');
  const { history, isLoading, error } = useOwnershipHistory(workItemId);

  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-body-sm font-semibold text-foreground">{t('heading')}</h3>

      {isLoading && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-3/4" />
        </div>
      )}

      {error && (
        <p role="alert" className="text-body-sm text-destructive">
          {t('errorPrefix')}: {error.message}
        </p>
      )}

      {!isLoading && !error && history.length === 0 && (
        <p className="text-caption text-muted-foreground">{t('empty')}</p>
      )}

      {!isLoading && !error && history.length > 0 && (
        <ul className="flex flex-col gap-2">
          {history.map((row) => (
            <li
              key={row.id}
              className="flex flex-col gap-1 rounded-md border border-border bg-card px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-body-sm text-foreground">
                  {row.previous_owner_id} → {row.new_owner_id}
                </span>
                <RelativeTime iso={row.changed_at} />
              </div>
              <span className="text-caption text-muted-foreground">
                {t('changedBy', { actor: row.changed_by })}
              </span>
              {row.reason && (
                <p className="text-caption text-muted-foreground">
                  <span className="font-medium">{t('reasonPrefix')}:</span> {row.reason}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
