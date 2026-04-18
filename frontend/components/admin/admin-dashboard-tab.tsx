'use client';

import { useAdminDashboard } from '@/hooks/use-admin';
import { Badge } from '@/components/ui/badge';

const HEALTH_VARIANT: Record<string, 'default' | 'secondary' | 'destructive'> = {
  healthy: 'default',
  degraded: 'secondary',
  error: 'destructive',
};

function StatCard({
  label,
  value,
  testId,
}: {
  label: string;
  value: number;
  testId: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-body-sm text-muted-foreground">{label}</p>
      <p data-testid={testId} className="mt-1 text-h2 font-semibold">
        {value}
      </p>
    </div>
  );
}

export function AdminDashboardTab() {
  const { dashboard, isLoading, error } = useAdminDashboard();

  if (isLoading) {
    return (
      <div data-testid="dashboard-skeleton" className="space-y-3 animate-pulse">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="h-24 rounded-lg bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div
        data-testid="dashboard-error"
        role="alert"
        className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-body-sm text-destructive"
      >
        Failed to load dashboard: {error?.message ?? 'Unknown error'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Members" value={dashboard.member_count} testId="dashboard-member-count" />
        <StatCard label="Projects" value={dashboard.project_count} testId="dashboard-project-count" />
        <StatCard label="Integrations" value={dashboard.integration_count} testId="dashboard-integration-count" />
        <StatCard label="Recent audit events" value={dashboard.recent_audit_count} testId="dashboard-audit-count" />
      </div>

      {/* Health pill */}
      <div className="flex items-center gap-2">
        <span className="text-body-sm font-medium text-muted-foreground">Workspace health:</span>
        <Badge
          data-testid="dashboard-health-pill"
          variant={HEALTH_VARIANT[dashboard.health] ?? 'secondary'}
        >
          {dashboard.health}
        </Badge>
      </div>

      {/* Work items by state bar */}
      {dashboard.total_active > 0 && (
        <div className="space-y-3">
          <p className="text-body-sm font-medium text-muted-foreground">
            Work items: {dashboard.total_active} active
          </p>
          <div className="flex h-3 w-full overflow-hidden rounded-full">
            {Object.entries(dashboard.work_items_by_state).map(([state, count]) => {
              const pct = (count / dashboard.total_active) * 100;
              return (
                <div
                  key={state}
                  data-testid={`dashboard-bar-${state}`}
                  style={{ width: `${pct}%` }}
                  className="bg-primary transition-all first:rounded-l-full last:rounded-r-full"
                  title={`${state}: ${count}`}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
