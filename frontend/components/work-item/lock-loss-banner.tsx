'use client';

/**
 * EP-17 G6 — Persistent banner shown when the user's section lock was
 * force-released or expired.
 *
 * - role="status" for screen-reader announcement
 * - Never auto-dismisses
 * - Reacquire button triggers parent's acquireLock flow
 */

import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface LockLossBannerProps {
  /** Called when the user clicks "Reacquire lock". */
  onReacquire: () => void;
  /** True while an acquire request is in-flight — disables the button. */
  isAcquiring?: boolean;
  className?: string;
}

export function LockLossBanner({ onReacquire, isAcquiring, className }: LockLossBannerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3',
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
      <div className="flex-1 text-sm">
        <p className="font-medium text-destructive">Your lock was released</p>
        <p className="mt-0.5 text-muted-foreground">
          Your unsaved changes are safe in this browser. Reacquire the lock to continue editing.
        </p>
      </div>
      <Button
        variant="destructive"
        size="sm"
        disabled={isAcquiring}
        onClick={onReacquire}
        aria-label="Reacquire lock"
      >
        {isAcquiring ? 'Acquiring…' : 'Reacquire lock'}
      </Button>
    </div>
  );
}
