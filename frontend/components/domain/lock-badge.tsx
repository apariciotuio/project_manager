import { cn } from '@/lib/utils';
import { Lock } from 'lucide-react';

interface LockBadgeProps {
  locked: boolean;
  lockedBy?: string;
  className?: string;
}

export function LockBadge({ locked, lockedBy, className }: LockBadgeProps) {
  if (!locked) return null;

  return (
    <span
      role="img"
      aria-label={lockedBy ? `Bloqueado por ${lockedBy}` : 'Bloqueado'}
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-severity-warning text-severity-warning-foreground px-2 py-0.5 text-xs font-medium',
        className
      )}
    >
      <Lock className="h-3 w-3" aria-hidden />
      {lockedBy ? lockedBy : 'Bloqueado'}
    </span>
  );
}
