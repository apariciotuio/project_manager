'use client';

/**
 * EP-17 G3 — LockBanner: inline banner shown when a section is locked by another user.
 *
 * Inline component (not a modal). Communicates read-only state.
 * Optional onRequestUnlock callback shows a "Solicitar desbloqueo" button.
 */

import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/domain/relative-time';
import { cn } from '@/lib/utils';

interface LockBannerProps {
  holderDisplayName: string;
  lockedSince: string; // ISO-8601
  expiresAt?: string; // ISO-8601, optional
  onRequestUnlock?: () => void;
  className?: string;
}

export function LockBanner({
  holderDisplayName,
  lockedSince,
  expiresAt,
  onRequestUnlock,
  className,
}: LockBannerProps) {
  return (
    <div
      role="status"
      aria-label={`Bloqueado por ${holderDisplayName} — solo lectura`}
      className={cn(
        'flex items-center justify-between gap-3 rounded-md bg-severity-warning/10 px-3 py-2 text-body-sm',
        className,
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Lock className="h-4 w-4 shrink-0 text-severity-warning-foreground" aria-hidden />
        <span className="truncate">
          <strong>{holderDisplayName}</strong>
          {' '}está editando esta sección
          {' · '}
          <RelativeTime iso={lockedSince} />
          {expiresAt !== undefined && (
            <>
              {' · '}expira <RelativeTime iso={expiresAt} />
            </>
          )}
        </span>
      </div>

      {onRequestUnlock !== undefined && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRequestUnlock}
          className="shrink-0"
        >
          Solicitar desbloqueo
        </Button>
      )}
    </div>
  );
}
