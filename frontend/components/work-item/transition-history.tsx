'use client';

import { useTranslations } from 'next-intl';
import { RelativeTime } from '@/components/domain/relative-time';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useTransitions } from '@/hooks/work-item/use-transitions';
import type { WorkItemState } from '@/lib/types/work-item';

export interface TransitionHistoryProps {
  workItemId: string;
}

export function TransitionHistory({ workItemId }: TransitionHistoryProps) {
  const t = useTranslations('workspace.itemDetail.audit.transitions');
  const tStates = useTranslations('workspace.itemDetail.transitions');
  const { transitions, isLoading, error } = useTransitions(workItemId);

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

      {!isLoading && !error && transitions.length === 0 && (
        <p className="text-caption text-muted-foreground">{t('empty')}</p>
      )}

      {!isLoading && !error && transitions.length > 0 && (
        <ul className="flex flex-col gap-2">
          {transitions.map((row) => (
            <li
              key={row.id}
              className="flex flex-col gap-1 rounded-md border border-border bg-card px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-body-sm text-foreground">
                  {tStates(row.from_state as WorkItemState)} → {tStates(row.to_state as WorkItemState)}
                </span>
                <RelativeTime iso={row.triggered_at} />
              </div>
              <div className="flex items-center gap-2 text-caption text-muted-foreground">
                {row.actor_id && <span>{t('actor', { actor: row.actor_id })}</span>}
                {row.is_override && <Badge variant="secondary">{t('override')}</Badge>}
              </div>
              {row.transition_reason && (
                <p className="text-caption text-muted-foreground">
                  <span className="font-medium">{t('reasonPrefix')}:</span> {row.transition_reason}
                </p>
              )}
              {row.is_override && row.override_justification && (
                <p className="text-caption text-muted-foreground italic">
                  {row.override_justification}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
