'use client';

import type { PipelineColumn as PipelineColumnData } from '@/lib/api/pipeline';
import { PipelineCard } from './pipeline-card';

interface PipelineColumnProps {
  column: PipelineColumnData;
  label: string;
}

function AgingBadge({ avgAgeDays, state }: { avgAgeDays: number; state: string }) {
  if (avgAgeDays <= 7) return null;
  const severity = avgAgeDays > 14 ? 'red' : 'amber';
  return (
    <span
      data-testid={`aging-badge-${state}`}
      data-severity={severity}
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        severity === 'red'
          ? 'bg-destructive/10 text-destructive'
          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
      ].join(' ')}
    >
      {Math.round(avgAgeDays)}d avg
    </span>
  );
}

export function PipelineColumn({ column, label }: PipelineColumnProps) {
  return (
    <div
      data-testid={`pipeline-column-${column.state}`}
      className="flex flex-col min-w-0 flex-1 md:min-w-[200px] md:max-w-[280px]"
    >
      {/* Column header */}
      <div className="flex items-center justify-between gap-2 mb-3 pb-2 border-b border-border">
        <span className="text-sm font-medium text-foreground truncate">{label}</span>
        <div className="flex items-center gap-1 shrink-0">
          <AgingBadge avgAgeDays={column.avg_age_days} state={column.state} />
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {column.count}
          </span>
        </div>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-2">
        {column.items.map((item) => (
          <PipelineCard key={item.id} item={item} />
        ))}
        {column.items.length === 0 && column.count === 0 && (
          <p className="text-xs text-muted-foreground italic py-2 text-center">—</p>
        )}
      </div>
    </div>
  );
}
