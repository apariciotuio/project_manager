import { useTranslations } from 'next-intl';

interface StateDistributionChartProps {
  byState: Record<string, number>;
}

const STATE_COLORS: Record<string, string> = {
  draft: 'bg-slate-400',
  in_clarification: 'bg-blue-400',
  in_review: 'bg-yellow-400',
  changes_requested: 'bg-orange-400',
  partially_validated: 'bg-indigo-400',
  ready: 'bg-green-500',
  exported: 'bg-emerald-600',
};

/**
 * EP-09 — Divided bar chart for items by state.
 * No external chart library — pure CSS flex segments.
 */
export function StateDistributionChart({ byState }: StateDistributionChartProps) {
  const tDash = useTranslations('workspace.dashboard');
  const total = Object.values(byState).reduce((a, b) => a + b, 0);
  const entries = Object.entries(byState).filter(([, v]) => v > 0);

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <h3 className="text-body font-semibold text-foreground">
        {tDash('stateDistribution.title')}
      </h3>

      {total === 0 ? (
        <p className="text-body-sm text-muted-foreground">—</p>
      ) : (
        <>
          {/* Divided bar */}
          <div
            role="img"
            aria-label={tDash('stateDistribution.title')}
            data-testid="state-distribution-bar"
            className="flex h-4 w-full overflow-hidden rounded-full"
          >
            {entries.map(([state, count]) => {
              const pct = (count / total) * 100;
              return (
                <div
                  key={state}
                  title={`${state}: ${count}`}
                  style={{ width: `${pct}%` }}
                  className={`${STATE_COLORS[state] ?? 'bg-gray-400'} shrink-0`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <ul className="flex flex-wrap gap-x-4 gap-y-1">
            {entries.map(([state, count]) => (
              <li key={state} className="flex items-center gap-1.5 text-body-sm text-muted-foreground">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full shrink-0 ${STATE_COLORS[state] ?? 'bg-gray-400'}`}
                />
                <span>{state}</span>
                <span className="tabular-nums font-medium text-foreground">{count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
