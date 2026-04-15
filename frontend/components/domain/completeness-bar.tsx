import { cn } from '@/lib/utils';
import type { CompletenessLevel } from './level-badge';

const LEVEL_CLASSES: Record<CompletenessLevel, string> = {
  low: 'bg-level-low',
  medium: 'bg-level-medium',
  high: 'bg-level-high',
  ready: 'bg-level-ready',
};

interface CompletenessBarProps {
  level: CompletenessLevel;
  percent: number;
  showLabel?: boolean;
  className?: string;
}

export function CompletenessBar({
  level,
  percent,
  showLabel = false,
  className,
}: CompletenessBarProps) {
  const clamped = Math.max(0, Math.min(100, percent));

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Completitud: ${clamped}%`}
        className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn('h-full rounded-full transition-all', LEVEL_CLASSES[level])}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-caption w-8 text-right">{clamped}%</span>
      )}
    </div>
  );
}
