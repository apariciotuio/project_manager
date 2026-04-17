import { useTranslations } from 'next-intl';
import type { DashboardWorkItems } from '@/lib/types/work-item';

interface DashboardSummaryProps {
  data: DashboardWorkItems;
}

/**
 * EP-09 — Summary cards: total items + avg completeness.
 */
export function DashboardSummary({ data }: DashboardSummaryProps) {
  const tDash = useTranslations('workspace.dashboard');

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <SummaryCard
        label={tDash('summary.total')}
        value={String(data.total)}
        testId="summary-total"
      />
      <SummaryCard
        label={tDash('summary.avgCompleteness')}
        value={`${Math.round(data.avg_completeness)}%`}
        testId="summary-avg-completeness"
      />
    </div>
  );
}

interface SummaryCardProps {
  label: string;
  value: string;
  testId?: string;
}

function SummaryCard({ label, value, testId }: SummaryCardProps) {
  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-border bg-card p-4 flex flex-col gap-1"
    >
      <p className="text-body-sm text-muted-foreground">{label}</p>
      <p className="text-h2 font-bold text-foreground tabular-nums">{value}</p>
    </div>
  );
}
