'use client';

/**
 * EP-17 G6 — Panel shown to the lock holder when an unlock request arrives.
 *
 * - NOT dismissible by Escape or click-outside (role="alertdialog", no onKeyDown handler)
 * - Countdown derived from request.expires_at
 * - Release: calls respond API with action=accept, notifies onRespond('release')
 * - Ignore: calls respond API with action=decline, notifies onRespond('ignore')
 */

import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { respondToUnlockRequest } from '@/lib/api/lock-api';
import type { UnlockRequestDTO } from '@/lib/types/lock';

interface HolderResponsePanelProps {
  sectionId: string;
  request: UnlockRequestDTO;
  requesterDisplayName: string;
  onRespond: (decision: 'release' | 'ignore') => void;
}

function formatCountdown(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function HolderResponsePanel({
  sectionId,
  request,
  requesterDisplayName,
  onRespond,
}: HolderResponsePanelProps) {
  const { toast } = useToast();
  const expiresAt = new Date(request.expires_at).getTime();
  const [remaining, setRemaining] = useState(() => expiresAt - Date.now());
  const [submitting, setSubmitting] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      const r = expiresAt - Date.now();
      setRemaining(r);
      if (r <= 0 && intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }, 1000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, [expiresAt]);

  async function handleDecision(decision: 'release' | 'ignore') {
    if (submitting) return;
    setSubmitting(true);
    try {
      await respondToUnlockRequest(sectionId, {
        request_id: request.id,
        action: decision === 'release' ? 'accept' : 'decline',
      });
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
      onRespond(decision);
    } catch {
      toast({ title: 'No se pudo procesar la respuesta. Inténtalo de nuevo.', variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="alertdialog"
      aria-modal="false"
      aria-label={`${requesterDisplayName} quiere editar esta sección`}
      className="rounded-lg border border-border bg-card p-4 shadow-md space-y-3"
    >
      <div className="space-y-1">
        <p className="text-body font-semibold">
          {requesterDisplayName} quiere editar esta sección
        </p>
        <p className="text-body-sm text-muted-foreground">
          Motivo: {request.reason}
        </p>
        <p className="text-caption text-muted-foreground">
          Se liberará automáticamente en{' '}
          <span className="font-mono">{formatCountdown(remaining)}</span>
        </p>
      </div>

      <div className="flex gap-2">
        <Button
          variant="destructive"
          size="sm"
          disabled={submitting}
          onClick={() => handleDecision('release')}
        >
          Liberar bloqueo
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={submitting}
          onClick={() => handleDecision('ignore')}
        >
          Ignorar
        </Button>
      </div>
    </div>
  );
}
