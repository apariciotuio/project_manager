import { cn } from '@/lib/utils';
import type { BadgeSize } from './state-badge';

export type Tier = 1 | 2 | 3 | 4;

const TIER_CLASSES: Record<Tier, string> = {
  1: 'bg-tier-1 text-tier-1-foreground',
  2: 'bg-tier-2 text-tier-2-foreground',
  3: 'bg-tier-3 text-tier-3-foreground',
  4: 'bg-tier-4 text-tier-4-foreground',
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'h-4 w-6 text-xs',
  md: 'h-5 w-7 text-body-sm',
  lg: 'h-6 w-9 text-body',
};

interface TierBadgeProps {
  tier: Tier;
  size?: BadgeSize;
  className?: string;
}

export function TierBadge({ tier, size = 'md', className }: TierBadgeProps) {
  return (
    <span
      role="img"
      aria-label={`Prioridad ${tier}`}
      className={cn(
        'inline-flex items-center justify-center rounded font-semibold',
        TIER_CLASSES[tier],
        SIZE_CLASSES[size],
        className
      )}
    >
      P{tier}
    </span>
  );
}
