import { cn } from '@/lib/utils';
import type { BadgeSize } from './state-badge';

export type CompletenessLevel = 'low' | 'medium' | 'high' | 'ready';

const LEVEL_CONFIG: Record<CompletenessLevel, { label: string; className: string }> = {
  low: {
    label: 'Bajo',
    className: 'bg-level-low text-level-low-foreground',
  },
  medium: {
    label: 'Medio',
    className: 'bg-level-medium text-level-medium-foreground',
  },
  high: {
    label: 'Alto',
    className: 'bg-level-high text-level-high-foreground',
  },
  ready: {
    label: 'Listo',
    className: 'bg-level-ready text-level-ready-foreground',
  },
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-1 text-body-sm',
  lg: 'px-2.5 py-1.5 text-body',
};

interface LevelBadgeProps {
  level: CompletenessLevel;
  size?: BadgeSize;
  className?: string;
}

export function LevelBadge({ level, size = 'md', className }: LevelBadgeProps) {
  const config = LEVEL_CONFIG[level];

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        config.className,
        SIZE_CLASSES[size],
        className
      )}
    >
      {config.label}
    </span>
  );
}
