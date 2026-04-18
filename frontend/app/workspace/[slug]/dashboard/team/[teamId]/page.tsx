'use client';

/**
 * EP-09 — Team dashboard.
 * Route: /workspace/{slug}/dashboard/team/{teamId}
 * Uses `recent_ready_items` field (not `velocity` — field was renamed in BE).
 */
import { useTranslations } from 'next-intl';
import { PageContainer } from '@/components/layout/page-container';
import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { InlineError } from '@/components/layout/inline-error';
import { useTeamDashboard } from '@/hooks/use-team-dashboard';

interface TeamDashboardPageProps {
  params: { slug: string; teamId: string };
}

function StatCard({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div data-testid={testId} className="rounded-lg border border-border bg-card p-4 flex flex-col gap-1">
      <span className="text-2xl font-bold text-foreground">{value}</span>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}

function StateDistribution({ data, testId }: { data: Record<string, number>; testId: string }) {
  const entries = Object.entries(data).filter(([, v]) => v > 0);
  return (
    <div data-testid={testId} className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-col gap-2">
        {entries.map(([state, count]) => (
          <div key={state} className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground capitalize">{state.replace(/_/g, ' ')}</span>
            <span className="font-medium text-foreground">{count}</span>
          </div>
        ))}
        {entries.length === 0 && (
          <p className="text-sm text-muted-foreground italic">—</p>
        )}
      </div>
    </div>
  );
}

export default function TeamDashboardPage({ params }: TeamDashboardPageProps) {
  const t = useTranslations('workspace.dashboard.team');
  const { teamId } = params;

  const { data, isLoading, error, refetch } = useTeamDashboard(teamId);

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      <h1 className="text-h2 font-semibold text-foreground">{t('title')}</h1>

      {isLoading && (
        <div data-testid="team-dashboard-skeleton">
          <SkeletonLoader variant="widget" count={4} />
        </div>
      )}

      {!isLoading && error && (
        <div data-testid="team-dashboard-error">
          <InlineError message={t('error')} onRetry={refetch} />
        </div>
      )}

      {!isLoading && !error && data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {/* recent_ready_items — approximation of velocity (items in 'ready' state, updated last 30d) */}
            <StatCard
              testId="team-dashboard-recent-ready"
              label={t('recentReady')}
              value={data.recent_ready_items}
            />
            <StatCard
              testId="team-dashboard-blocked"
              label={t('blocked')}
              value={data.blocked_count}
            />
            <StatCard
              testId="team-dashboard-pending-reviews"
              label={t('pendingReviews')}
              value={data.pending_reviews}
            />
          </div>

          <div>
            <h2 className="text-sm font-medium text-foreground mb-3">{t('ownedByState')}</h2>
            <StateDistribution
              data={data.owned_by_state}
              testId="team-dashboard-state-distribution"
            />
          </div>
        </>
      )}
    </PageContainer>
  );
}
