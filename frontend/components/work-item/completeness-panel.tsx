'use client';

import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { LevelBadge } from '@/components/domain/level-badge';
import { CompletenessBar } from '@/components/domain/completeness-bar';
import { SeverityBadge } from '@/components/domain/severity-badge';
import { useCompleteness } from '@/hooks/work-item/use-completeness';
import { useGaps } from '@/hooks/work-item/use-gaps';
import type { CompletenessLevel } from '@/lib/types/specification';
import { cn } from '@/lib/utils';

interface CompletenessPanelProps {
  workItemId: string;
}

function scoreToLevel(score: number): CompletenessLevel {
  if (score >= 90) return 'ready';
  if (score >= 70) return 'high';
  if (score >= 34) return 'medium';
  return 'low';
}

export function CompletenessPanel({ workItemId }: CompletenessPanelProps) {
  const t = useTranslations('workspace.itemDetail.completeness');
  const { completeness, isLoading: completenessLoading } = useCompleteness(workItemId);
  const { gapReport, isLoading: gapsLoading } = useGaps(workItemId);

  const isLoading = completenessLoading || gapsLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 rounded-lg border border-border p-4" aria-busy="true">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-16 w-16 rounded-full self-center" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
      </div>
    );
  }

  if (!completeness) {
    return null;
  }

  const level = completeness.level as CompletenessLevel;
  const gapsByDimension = new Map(
    (gapReport?.findings ?? []).map((f) => [f.dimension, f])
  );

  return (
    <aside
      className="flex flex-col gap-4 rounded-lg border border-border p-4 self-start sticky top-4"
      aria-label={t('title')}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{t('title')}</h3>
        {completeness.cached && (
          <Badge variant="outline" className="text-xs" data-testid="cached-badge">
            {t('cached')}
          </Badge>
        )}
      </div>

      {/* Overall score */}
      <div className="flex items-center gap-3">
        <div
          role="progressbar"
          aria-valuenow={completeness.score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${t('score')}: ${completeness.score}%`}
          className="relative h-16 w-16 shrink-0"
        >
          <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted" />
            <circle
              cx="32"
              cy="32"
              r="28"
              fill="none"
              stroke="currentColor"
              strokeWidth="6"
              strokeDasharray={`${2 * Math.PI * 28}`}
              strokeDashoffset={`${2 * Math.PI * 28 * (1 - completeness.score / 100)}`}
              strokeLinecap="round"
              className="text-primary transition-all duration-500"
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold">
            {completeness.score}
          </span>
        </div>
        <span data-testid="completeness-level-badge">
          <LevelBadge level={level} />
        </span>
      </div>

      {/* Dimension rows */}
      <div className="flex flex-col gap-2">
        {completeness.dimensions
          .filter((d) => d.applicable)
          .map((dim) => {
            const pct = Math.round(dim.score * 100);
            const dimLevel = scoreToLevel(pct);
            const gap = gapsByDimension.get(dim.dimension);
            const label = t(`dimension.${dim.dimension}`) ?? dim.dimension.replace(/_/g, ' ');

            return (
              <div
                key={dim.dimension}
                className="flex flex-col gap-0.5"
                data-testid="dimension-row"
              >
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span className="capitalize">{label}</span>
                  <span>{Math.round(dim.weight * 100)}%</span>
                </div>
                <CompletenessBar level={dimLevel} percent={pct} />
                {gap && (
                  <div className={cn('flex items-start gap-1 mt-0.5')}>
                    <SeverityBadge severity={gap.severity as 'blocking' | 'warning' | 'info'} size="sm" />
                    <p className="text-xs text-foreground">{gap.message}</p>
                  </div>
                )}
              </div>
            );
          })}
      </div>
    </aside>
  );
}
