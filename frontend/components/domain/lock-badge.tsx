import { cn } from '@/lib/utils';
import { Lock } from 'lucide-react';

interface LockBadgeProps {
  locked: boolean;
  lockedBy?: string;
  /** Number of locked sections (list-view summary). Defaults to 1 if omitted. */
  count?: number;
  /** True when the current user holds at least one of the locks. */
  heldByMe?: boolean;
  className?: string;
}

export function LockBadge({ locked, lockedBy, count, heldByMe, className }: LockBadgeProps) {
  if (!locked) return null;

  const label = buildLabel({ lockedBy, count, heldByMe });
  const ariaLabel = heldByMe
    ? 'Locked by me'
    : lockedBy
      ? `Bloqueado por ${lockedBy}`
      : count && count > 1
        ? `${count} section(s) locked`
        : 'Bloqueado';

  return (
    <span
      role="img"
      aria-label={ariaLabel}
      title={ariaLabel}
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-severity-warning text-severity-warning-foreground px-2 py-0.5 text-xs font-medium',
        className,
      )}
    >
      <Lock className="h-3 w-3" aria-hidden />
      {label}
    </span>
  );
}

function buildLabel({
  lockedBy,
  count,
  heldByMe,
}: {
  lockedBy?: string;
  count?: number;
  heldByMe?: boolean;
}): string {
  if (heldByMe) return 'Locked by me';
  if (lockedBy) return lockedBy;
  if (count && count > 1) return `${count} locked`;
  return 'Bloqueado';
}
