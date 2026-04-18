import { cn } from '@/lib/utils';

// Colour thresholds — single source of truth
const THRESHOLD_COMPLETE = 100;
const THRESHOLD_START = 0;

interface RollupBadgeProps {
  rollup_percent: number | null;
  stale?: boolean;
  className?: string;
}

export function RollupBadge({ rollup_percent, stale = false, className }: RollupBadgeProps) {
  if (rollup_percent === null) return null;

  const colourClass =
    rollup_percent >= THRESHOLD_COMPLETE
      ? 'rollup-complete bg-state-ready text-state-ready-foreground'
      : rollup_percent > THRESHOLD_START
        ? 'rollup-in-progress bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
        : 'rollup-neutral bg-muted text-muted-foreground';

  const ariaLabel = stale
    ? `${rollup_percent}% (recalculating)`
    : `${rollup_percent}% complete`;

  return (
    <span
      role="img"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        colourClass,
        className,
      )}
    >
      {rollup_percent}%
      {stale && (
        <span aria-hidden className="animate-spin text-[10px]">⟳</span>
      )}
    </span>
  );
}
