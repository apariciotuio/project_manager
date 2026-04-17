import { useTranslations } from 'next-intl';

interface TypeDistributionChartProps {
  byType: Record<string, number>;
}

const TYPE_COLORS: Record<string, string> = {
  idea: 'bg-violet-400',
  bug: 'bg-red-400',
  enhancement: 'bg-blue-400',
  task: 'bg-sky-400',
  initiative: 'bg-indigo-500',
  spike: 'bg-amber-400',
  business_change: 'bg-teal-400',
  requirement: 'bg-orange-400',
  milestone: 'bg-green-500',
  story: 'bg-cyan-400',
};

/**
 * EP-09 — Divided bar chart for items by type.
 * No external chart library — pure CSS flex segments.
 */
export function TypeDistributionChart({ byType }: TypeDistributionChartProps) {
  const tDash = useTranslations('workspace.dashboard');
  const total = Object.values(byType).reduce((a, b) => a + b, 0);
  const entries = Object.entries(byType).filter(([, v]) => v > 0);

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <h3 className="text-body font-semibold text-foreground">
        {tDash('typeDistribution.title')}
      </h3>

      {total === 0 ? (
        <p className="text-body-sm text-muted-foreground">—</p>
      ) : (
        <>
          {/* Divided bar */}
          <div
            role="img"
            aria-label={tDash('typeDistribution.title')}
            data-testid="type-distribution-bar"
            className="flex h-4 w-full overflow-hidden rounded-full"
          >
            {entries.map(([type, count]) => {
              const pct = (count / total) * 100;
              return (
                <div
                  key={type}
                  title={`${type}: ${count}`}
                  style={{ width: `${pct}%` }}
                  className={`${TYPE_COLORS[type] ?? 'bg-gray-400'} shrink-0`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <ul className="flex flex-wrap gap-x-4 gap-y-1">
            {entries.map(([type, count]) => (
              <li key={type} className="flex items-center gap-1.5 text-body-sm text-muted-foreground">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full shrink-0 ${TYPE_COLORS[type] ?? 'bg-gray-400'}`}
                />
                <span>{type}</span>
                <span className="tabular-nums font-medium text-foreground">{count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
