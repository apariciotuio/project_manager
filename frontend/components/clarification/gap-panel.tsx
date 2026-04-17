'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useGaps } from '@/hooks/work-item/use-gaps';
import type { GapFinding } from '@/lib/types/gap';
import { cn } from '@/lib/utils';
import { Loader2, X } from 'lucide-react';

interface GapPanelProps {
  workItemId: string;
  workItemVersion: number;
}

function severityOrder(s: GapFinding['severity']): number {
  return s === 'blocking' ? 0 : s === 'warning' ? 1 : 2;
}

export function GapPanel({ workItemId }: GapPanelProps) {
  const t = useTranslations('workspace.itemDetail.gaps');
  const { gapReport, isLoading, error, isReviewing, refetch, runAiReview } = useGaps(workItemId);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  function dismiss(key: string) {
    setDismissed((prev) => new Set(prev).add(key));
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-4 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t('loading')}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4" role="alert">
        <p className="text-sm text-destructive">{t('unavailable')}</p>
        <Button size="sm" variant="outline" className="mt-2" onClick={() => void refetch()}>
          {t('retry')}
        </Button>
      </div>
    );
  }

  const findings = (gapReport?.findings ?? [])
    .filter((f) => {
      const key = `${f.dimension}:${f.message}`;
      return !dismissed.has(key);
    })
    .sort((a, b) => severityOrder(a.severity) - severityOrder(b.severity));

  const score = gapReport?.score ?? 1;
  const scorePercent = Math.round(score * 100);

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* Completeness score */}
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{t('completeness')}</span>
        <span className="tabular-nums">{scorePercent}%</span>
      </div>

      {/* Findings list */}
      {findings.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('noGaps')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {findings.map((f) => {
            const key = `${f.dimension}:${f.message}`;
            return (
              <li key={key} className="flex items-start gap-2">
                {/* Severity indicator */}
                <span
                  className={cn(
                    'mt-1 h-2 w-2 shrink-0 rounded-full',
                    f.severity === 'blocking' && 'bg-destructive',
                    f.severity === 'warning' && 'bg-yellow-500',
                    f.severity === 'info' && 'bg-blue-400',
                  )}
                  aria-hidden
                />
                <div className="flex-1 min-w-0">
                  <span className="text-sm">{f.message}</span>
                  <div className="flex gap-1 mt-0.5">
                    <Badge variant="outline" className="text-xs px-1 py-0">
                      {f.source === 'llm' ? 'AI' : 'Rule'}
                    </Badge>
                  </div>
                </div>
                <button
                  type="button"
                  aria-label={`Dismiss: ${f.message}`}
                  className="shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={() => dismiss(key)}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* AI Review button */}
      {isReviewing ? (
        <p className="text-sm text-muted-foreground flex items-center gap-1">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {t('reviewing')}
        </p>
      ) : (
        <Button
          size="sm"
          variant="outline"
          onClick={() => void runAiReview()}
          aria-label={t('runAiReview')}
        >
          {t('runAiReview')}
        </Button>
      )}
    </div>
  );
}
