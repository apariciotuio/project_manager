'use client';

/**
 * EP-17 G7 — ForceReleaseDialog (admin only).
 *
 * Gated on currentUser.is_superadmin (capabilities.force_unlock pending RBAC — EP-10).
 * Requires reason (min 10 chars) AND confirmation checkbox before submit.
 *
 * NOTE: the backend force-release endpoint does not currently accept a reason
 * parameter (TODO in lock_controller.py). Reason is validated UI-side only
 * until BE adds the param.
 */

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/hooks/use-toast';
import { forceReleaseSectionLock } from '@/lib/api/lock-api';
import { ApiError } from '@/lib/types/auth';
import { RelativeTime } from '@/components/domain/relative-time';
import type { SectionLockDTO } from '@/lib/types/lock';
import type { AuthUser } from '@/lib/types/auth';

const MIN_REASON_LENGTH = 10;
const MAX_REASON_LENGTH = 1000;

interface ForceReleaseDialogProps {
  sectionId: string;
  lock: SectionLockDTO;
  holderDisplayName: string;
  currentUser: AuthUser;
  isOpen: boolean;
  onClose: () => void;
}

export function ForceReleaseDialog({
  sectionId,
  lock,
  holderDisplayName,
  currentUser,
  isOpen,
  onClose,
}: ForceReleaseDialogProps) {
  const { toast } = useToast();
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reasonValid = reason.trim().length >= MIN_REASON_LENGTH;
  const canSubmit = reasonValid && confirmed && !submitting;

  function handleOpenChange(open: boolean) {
    if (!open) {
      setReason('');
      setConfirmed(false);
      setError(null);
      onClose();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await forceReleaseSectionLock(sectionId);
      toast({ title: 'Bloqueo liberado correctamente.' });
      setReason('');
      setConfirmed(false);
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError('El servicio no está disponible. Inténtalo de nuevo en unos momentos.');
      } else {
        setError('No se pudo liberar el bloqueo. Inténtalo de nuevo.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  // Gate: only superadmin can force-release (capabilities.force_unlock pending RBAC)
  if (!currentUser.is_superadmin) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Forzar desbloqueo</DialogTitle>
          <DialogDescription>
            Vas a quitar el bloqueo de {holderDisplayName}. Sus cambios sin guardar se perderán.
          </DialogDescription>
        </DialogHeader>

        <p className="text-body-sm text-muted-foreground">
          Editando actualmente: <strong>{holderDisplayName}</strong>
          {' · '}Desde <RelativeTime iso={lock.acquired_at} />
          {' · '}Expira <RelativeTime iso={lock.expires_at} />
        </p>

        <form onSubmit={handleSubmit} noValidate>
          <div className="space-y-2">
            <Label htmlFor="force-release-reason">Motivo</Label>
            <Textarea
              id="force-release-reason"
              value={reason}
              onChange={(e) => {
                const val = e.target.value;
                if (val.length <= MAX_REASON_LENGTH) {
                  setReason(val);
                }
                setError(null);
              }}
              placeholder="Indica el motivo del desbloqueo forzado"
              rows={3}
            />
            <div className="flex justify-between">
              <p className="text-caption text-muted-foreground">Mínimo 10 caracteres</p>
              <p className="text-right text-caption text-muted-foreground">
                {reason.length}/{MAX_REASON_LENGTH}
              </p>
            </div>
          </div>

          <div className="mt-3 flex items-start gap-2">
            <Checkbox
              id="force-release-confirm"
              checked={confirmed}
              onCheckedChange={(v) => setConfirmed(v === true)}
            />
            <Label htmlFor="force-release-confirm" className="cursor-pointer leading-relaxed">
              Entiendo que los cambios sin guardar de {holderDisplayName} se perderán
            </Label>
          </div>

          {error !== null && (
            <div role="alert" className="mt-2 rounded-md bg-destructive/10 px-3 py-2 text-body-sm text-destructive">
              {error}
            </div>
          )}

          <DialogFooter className="mt-4">
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="destructive" disabled={!canSubmit}>
              {submitting ? 'Liberando…' : 'Forzar desbloqueo'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
