'use client';

/**
 * EP-09 — Pipeline view.
 * Route: /workspace/{slug}/pipeline
 * Consumes GET /api/v1/pipeline — funnel per workflow state.
 */
import { useTranslations } from 'next-intl';
import { PageContainer } from '@/components/layout/page-container';
import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { InlineError } from '@/components/layout/inline-error';
import { PipelineColumn } from '@/components/pipeline/pipeline-column';
import { PipelineCard } from '@/components/pipeline/pipeline-card';
import { usePipeline } from '@/hooks/use-pipeline';

interface PipelinePageProps {
  params: { slug: string };
}

const FSM_ORDER = ['draft', 'in_clarification', 'in_review', 'partially_validated', 'ready'] as const;

export default function PipelinePage({ params: _params }: PipelinePageProps) {
  const t = useTranslations('workspace.pipeline');
  const { data, isLoading, error, refetch } = usePipeline();

  const totalItems = data
    ? data.columns.reduce((sum, c) => sum + c.count, 0) + data.blocked_lane.length
    : 0;

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      <h1 className="text-h2 font-semibold text-foreground">{t('title')}</h1>

      {isLoading && (
        <div data-testid="pipeline-skeleton">
          <SkeletonLoader variant="card" count={5} />
        </div>
      )}

      {!isLoading && error && (
        <div data-testid="pipeline-error">
          <InlineError message={t('error')} onRetry={refetch} />
        </div>
      )}

      {!isLoading && !error && data && totalItems === 0 && (
        <div data-testid="pipeline-empty-state" className="py-12 text-center text-muted-foreground">
          {t('empty')}
        </div>
      )}

      {!isLoading && !error && data && totalItems > 0 && (
        <>
          {/* Main columns in FSM order */}
          <div className="flex flex-col gap-4 md:flex-row md:gap-3 overflow-x-auto pb-4">
            {FSM_ORDER.map((state) => {
              const col = data.columns.find((c) => c.state === state);
              if (!col) return null;
              return (
                <PipelineColumn
                  key={state}
                  column={col}
                  label={t(`columns.${state}` as Parameters<typeof t>[0])}
                />
              );
            })}
          </div>

          {/* Blocked lane */}
          {data.blocked_lane.length > 0 && (
            <div data-testid="pipeline-blocked-lane" className="border-t border-border pt-4">
              <h2 className="text-sm font-medium text-foreground mb-3">{t('blockedLane')}</h2>
              <div className="flex flex-wrap gap-2">
                {data.blocked_lane.map((item) => (
                  <PipelineCard key={item.id} item={item} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}
