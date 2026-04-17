'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { useForceReady } from '@/hooks/work-item/use-force-ready';
import type { WorkItemResponse } from '@/lib/types/work-item';

export interface ForceReadyModalProps {
  open: boolean;
  workItem: WorkItemResponse;
  onClose: () => void;
  onForced: (updated: WorkItemResponse) => void;
}

export function ForceReadyModal({ open, workItem, onClose, onForced }: ForceReadyModalProps) {
  const t = useTranslations('workspace.itemDetail.forceReady');
  const tCommon = useTranslations('common');

  const [justification, setJustification] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const { forceReady, isPending, error } = useForceReady(workItem.id);

  useEffect(() => {
    if (open) {
      setJustification('');
      setConfirmText('');
    }
  }, [open]);

  const canConfirm =
    justification.trim().length > 0 && confirmText === workItem.title && !isPending;

  async function handleConfirm() {
    if (!canConfirm) return;
    const updated = await forceReady(justification.trim());
    if (updated) {
      onForced(updated);
      onClose();
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('dialogTitle')}</DialogTitle>
          <DialogDescription>{t('dialogDescription')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="force-ready-justification">{t('justificationLabel')}</Label>
            <Textarea
              id="force-ready-justification"
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              placeholder={t('justificationPlaceholder')}
              rows={3}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="force-ready-confirm">{t('typeToConfirmLabel')}</Label>
            <Input
              id="force-ready-confirm"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={workItem.title}
              autoComplete="off"
            />
          </div>

          {error && (
            <p role="alert" className="text-body-sm text-destructive">
              {t('errorPrefix')}: {error.message}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
            {tCommon('cancel')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => void handleConfirm()}
            disabled={!canConfirm}
          >
            {isPending ? tCommon('saving') : t('confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
