'use client';

import { RefreshCw } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageContainer } from '@/components/layout/page-container';
import { DashboardSummary } from '@/components/dashboard/dashboard-summary';
import { StateDistributionChart } from '@/components/dashboard/state-distribution-chart';
import { TypeDistributionChart } from '@/components/dashboard/type-distribution-chart';
import { RecentActivityFeed } from '@/components/dashboard/recent-activity-feed';
import { useDashboard } from '@/hooks/use-dashboard';

interface DashboardPageProps {
  params: { slug: string };
}

export default function DashboardPage({ params }: DashboardPageProps) {
  const { slug } = params;
  const tDash = useTranslations('workspace.dashboard');
  const { data, isLoading, error, refresh } = useDashboard();

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-h2 font-semibold text-foreground">
          {tDash('title')}
        </h1>
        <Button
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={isLoading}
          aria-label={tDash('retry')}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden />
          {tDash('retry')}
        </Button>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div data-testid="dashboard-skeleton" className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-lg" />
            ))}
          </div>
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div role="alert" className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-body-sm text-destructive">{tDash('error')}</p>
          <Button variant="outline" size="sm" onClick={refresh} className="mt-2">
            {tDash('retry')}
          </Button>
        </div>
      )}

      {/* Dashboard content */}
      {data && !isLoading && (
        <>
          {/* Summary cards */}
          <DashboardSummary data={data.work_items} />

          {/* Charts */}
          <div className="grid gap-4 md:grid-cols-2">
            <StateDistributionChart byState={data.work_items.by_state} />
            <TypeDistributionChart byType={data.work_items.by_type} />
          </div>

          {/* Recent activity */}
          <RecentActivityFeed items={data.recent_activity} slug={slug} />
        </>
      )}
    </PageContainer>
  );
}
