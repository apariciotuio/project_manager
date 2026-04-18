'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useVersions } from '@/hooks/work-item/use-versions';
import { DiffContent, DiffViewer } from './diff-viewer';
import type { WorkItemVersionSummary } from '@/lib/api/versions';

interface VersionHistoryPanelProps {
  workItemId: string;
  /** When passed, only owners/admins should see this panel — enforce at call site */
}

const TRIGGER_LABELS: Record<string, string> = {
  content_edit: 'content_edit',
  state_transition: 'state_transition',
  review_outcome: 'review_outcome',
  breakdown_change: 'breakdown_change',
  manual: 'manual',
  ai_suggestion: 'ai_suggestion',
};

function triggerBadgeVariant(
  trigger: string,
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (trigger === 'ai_suggestion') return 'secondary';
  if (trigger === 'state_transition') return 'outline';
  return 'default';
}

export function VersionHistoryPanel({ workItemId }: VersionHistoryPanelProps) {
  const t = useTranslations('workspace.itemDetail.versions');
  const { versions, isLoading, error, hasMore, loadMore } = useVersions(workItemId);
  const [diffVersion, setDiffVersion] = useState<number | null>(null);

  if (isLoading && versions.length === 0) {
    return (
      <div className="flex flex-col gap-3 py-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <p role="alert" className="text-sm text-destructive py-4">
        {t('loadError')}
      </p>
    );
  }

  if (versions.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">{t('empty')}</p>;
  }

  const latestVersion = versions[0];
  const hasPrevious = versions.length >= 2;

  return (
    <div className="flex flex-col gap-4">
      {latestVersion && hasPrevious && (
        <section
          aria-label={t('initialDiffPreview')}
          className="rounded border border-border bg-background p-4"
        >
          <header className="flex items-center justify-between gap-4 pb-2">
            <h3 className="text-sm font-semibold">
              {t('diffTitle', { version: latestVersion.version_number })}
            </h3>
            <span className="text-xs text-muted-foreground">
              {t('latestVsPrevious')}
            </span>
          </header>
          <DiffContent
            workItemId={workItemId}
            versionNumber={latestVersion.version_number}
            active
          />
        </section>
      )}

      <ul className="flex flex-col divide-y" aria-label={t('list')}>
        {versions.map((v: WorkItemVersionSummary) => (
          <li key={v.id} className="py-3 flex items-start justify-between gap-4">
            <div className="flex flex-col gap-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium">v{v.version_number}</span>
                <Badge variant={triggerBadgeVariant(v.trigger)} className="text-xs">
                  {TRIGGER_LABELS[v.trigger] ?? v.trigger}
                </Badge>
                {v.archived && (
                  <Badge variant="outline" className="text-xs text-muted-foreground">
                    {t('archived')}
                  </Badge>
                )}
              </div>
              {v.commit_message && (
                <span className="text-sm text-muted-foreground truncate">{v.commit_message}</span>
              )}
              <span className="text-xs text-muted-foreground">
                {new Date(v.created_at).toLocaleString()}
              </span>
            </div>

            <Button
              size="sm"
              variant="outline"
              className="shrink-0"
              aria-label={t('viewDiff')}
              onClick={() => setDiffVersion(v.version_number)}
            >
              {t('viewDiff')}
            </Button>
          </li>
        ))}
      </ul>

      {hasMore && (
        <Button
          variant="ghost"
          size="sm"
          aria-label={t('loadMore')}
          onClick={() => void loadMore()}
          disabled={isLoading}
        >
          {t('loadMore')}
        </Button>
      )}

      <DiffViewer
        workItemId={workItemId}
        versionNumber={diffVersion}
        open={diffVersion !== null}
        onClose={() => setDiffVersion(null)}
      />
    </div>
  );
}
