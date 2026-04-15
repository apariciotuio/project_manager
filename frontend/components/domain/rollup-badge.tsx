import { cn } from '@/lib/utils';

interface RollupBadgeProps {
  total: number;
  ready: number;
  className?: string;
}

export function RollupBadge({ total, ready, className }: RollupBadgeProps) {
  const pct = total > 0 ? Math.round((ready / total) * 100) : 0;
  const isComplete = ready === total && total > 0;

  return (
    <span
      role="img"
      aria-label={`${ready} de ${total} elementos listos (${pct}%)`}
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        isComplete
          ? 'bg-state-ready text-state-ready-foreground'
          : 'bg-muted text-muted-foreground',
        className
      )}
    >
      {ready}/{total}
    </span>
  );
}
