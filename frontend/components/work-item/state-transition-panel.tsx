'use client';

import { useState } from 'react';
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
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { getAvailableTransitions } from '@/lib/state-machine';
import { useTransitionState } from '@/hooks/work-item/use-transition-state';
import type { WorkItemResponse, WorkItemState } from '@/lib/types/work-item';

export interface StateTransitionPanelProps {
  workItem: WorkItemResponse;
  /** Called with the updated work item after a successful transition so the parent can refetch / re-render. */
  onTransition: (updated: WorkItemResponse) => void;
}

export function StateTransitionPanel({ workItem, onTransition }: StateTransitionPanelProps) {
  const t = useTranslations('workspace.itemDetail.transitions');
  const tCommon = useTranslations('common');

  const [target, setTarget] = useState<WorkItemState | null>(null);
  const [reason, setReason] = useState('');
  const { transition, isPending, error } = useTransitionState(workItem.id);

  const available = getAvailableTransitions(workItem.state);

  function openDialog(next: WorkItemState) {
    setReason('');
    setTarget(next);
  }

  function closeDialog() {
    setTarget(null);
    setReason('');
  }

  async function handleConfirm() {
    if (!target) return;
    const trimmedReason = reason.trim();
    const updated = await transition(target, trimmedReason === '' ? undefined : trimmedReason);
    if (updated) {
      onTransition(updated);
      closeDialog();
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-body-sm font-semibold text-foreground">{t('heading')}</h3>
        <span
          role="status"
          aria-label={`${t('heading')}: ${t(workItem.state)}`}
          className="rounded-full bg-muted px-2 py-0.5 text-caption font-medium text-muted-foreground"
        >
          {t(workItem.state)}
        </span>
      </div>

      {available.length === 0 ? (
        <p className="text-caption text-muted-foreground">{t('noneAvailable')}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {available.map((next) => (
            <Button
              key={next}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => openDialog(next)}
              aria-label={`${t('buttonPrefix')} ${t(next)}`}
            >
              {`${t('buttonPrefix')} ${t(next)}`}
            </Button>
          ))}
        </div>
      )}

      <Dialog open={target !== null} onOpenChange={(open) => { if (!open) closeDialog(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {target ? t('dialogTitle', { target: t(target) }) : ''}
            </DialogTitle>
            <DialogDescription>{t('dialogDescription')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="transition-reason">{t('reasonLabel')}</Label>
            <Textarea
              id="transition-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t('reasonPlaceholder')}
              rows={3}
            />
          </div>

          {error && (
            <p role="alert" className="text-body-sm text-destructive">
              {t('errorPrefix')}: {error.message}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeDialog} disabled={isPending}>
              {tCommon('cancel')}
            </Button>
            <Button type="button" onClick={() => void handleConfirm()} disabled={isPending}>
              {isPending ? tCommon('saving') : t('confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
