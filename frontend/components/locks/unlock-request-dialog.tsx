'use client';

/**
 * EP-17 G5 — Dialog for requesting that the current lock holder releases their lock.
 *
 * Props:
 *   sectionId          — section whose lock we're requesting to be released
 *   holderDisplayName  — display name of the current lock holder
 *   isOpen             — controlled open state
 *   onClose            — called on cancel or successful submit
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
import { useToast } from '@/hooks/use-toast';
import { requestSectionUnlock } from '@/lib/api/lock-api';
import { ApiError } from '@/lib/types/auth';

const MAX_REASON_LENGTH = 500;

interface UnlockRequestDialogProps {
  sectionId: string;
  holderDisplayName: string;
  isOpen: boolean;
  onClose: () => void;
}

export function UnlockRequestDialog({
  sectionId,
  holderDisplayName,
  isOpen,
  onClose,
}: UnlockRequestDialogProps) {
  const { toast } = useToast();
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmedReason = reason.trim();
  const canSubmit = trimmedReason.length > 0 && trimmedReason.length <= MAX_REASON_LENGTH && !submitting;

  function handleOpenChange(open: boolean) {
    if (!open) {
      setReason('');
      setError(null);
      onClose();
    }
  }

  function handleReasonChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    if (val.length <= MAX_REASON_LENGTH) {
      setReason(val);
    }
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await requestSectionUnlock(sectionId, trimmedReason);
      toast({
        title: `Solicitud enviada a ${holderDisplayName}. Recibirás una notificación cuando responda.`,
      });
      setReason('');
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError('Ya existe una solicitud pendiente para esta sección.');
        } else if (err.status === 429) {
          const retryAfter = typeof err.details === 'object' && err.details !== null
            ? (err.details as Record<string, unknown>)['retry_after']
            : undefined;
          const minutes = retryAfter ? Math.ceil(Number(retryAfter) / 60) : 5;
          setError(`Demasiadas solicitudes. Inténtalo de nuevo en ${minutes} minutos.`);
        } else {
          setError('No se pudo enviar la solicitud. Inténtalo de nuevo.');
        }
      } else {
        setError('No se pudo enviar la solicitud. Inténtalo de nuevo.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Solicitar que {holderDisplayName} libere el bloqueo
          </DialogTitle>
          <DialogDescription>
            Envía una solicitud a {holderDisplayName} para que libere el bloqueo de esta sección.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate>
          <div className="space-y-2">
            <Label htmlFor="unlock-reason">
              Motivo de la solicitud
            </Label>
            <Textarea
              id="unlock-reason"
              value={reason}
              onChange={handleReasonChange}
              placeholder="Explica por qué necesitas editar esta sección"
              required
              aria-required="true"
              rows={4}
            />
            <p className="text-right text-caption text-muted-foreground">
              {reason.length}/{MAX_REASON_LENGTH}
            </p>
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
            <Button type="submit" disabled={!canSubmit}>
              {submitting ? 'Enviando…' : 'Enviar solicitud'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
