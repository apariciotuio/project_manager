'use client';

/**
 * EP-09 — Person dashboard.
 * Route: /workspace/{slug}/dashboard/me
 * AuthZ: BE returns 403 if user_id != caller (handled by hook).
 */
import { useTranslations } from 'next-intl';
import { useAuth } from '@/app/providers/auth-provider';
import { PageContainer } from '@/components/layout/page-container';
import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { InlineError } from '@/components/layout/inline-error';
import { EmptyState } from '@/components/layout/empty-state';
import { usePersonDashboard } from '@/hooks/use-person-dashboard';

interface PersonDashboardPageProps {
  params: { slug: string };
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

export default function PersonDashboardPage({ params: _params }: PersonDashboardPageProps) {
  const t = useTranslations('workspace.dashboard.person');
  const { user } = useAuth();
  const userId = user?.id ?? '';

  const { data, isLoading, error, isForbidden, refetch } = usePersonDashboard(userId);

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      <h1 className="text-h2 font-semibold text-foreground">{t('title')}</h1>

      {isLoading && (
        <div data-testid="person-dashboard-skeleton">
          <SkeletonLoader variant="widget" count={4} />
        </div>
      )}

      {!isLoading && isForbidden && (
        <div data-testid="person-dashboard-no-permission">
          <EmptyState variant="no-access" heading={t('noPermission')} />
        </div>
      )}

      {!isLoading && !isForbidden && error && (
        <div data-testid="person-dashboard-error">
          <InlineError message={t('error')} onRetry={refetch} />
        </div>
      )}

      {!isLoading && !isForbidden && !error && data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              testId="person-dashboard-inbox"
              label={t('inbox')}
              value={data.inbox_count}
            />
            <StatCard
              testId="person-dashboard-pending-reviews"
              label={t('pendingReviews')}
              value={data.pending_reviews_count}
            />
          </div>

          <div>
            <h2 className="text-sm font-medium text-foreground mb-3">{t('ownedByState')}</h2>
            <StateDistribution
              data={data.owned_by_state}
              testId="person-dashboard-state-distribution"
            />
          </div>
        </>
      )}
    </PageContainer>
  );
}
