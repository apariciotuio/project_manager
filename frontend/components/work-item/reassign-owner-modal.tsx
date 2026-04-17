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
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useWorkspaceMembers } from '@/hooks/use-workspace-members';
import { useReassignOwner } from '@/hooks/work-item/use-reassign-owner';
import type { WorkItemResponse } from '@/lib/types/work-item';

export interface ReassignOwnerModalProps {
  open: boolean;
  workItem: WorkItemResponse;
  onClose: () => void;
  onReassigned: (updated: WorkItemResponse) => void;
}

export function ReassignOwnerModal({
  open,
  workItem,
  onClose,
  onReassigned,
}: ReassignOwnerModalProps) {
  const t = useTranslations('workspace.itemDetail.reassign');
  const tCommon = useTranslations('common');

  const { members, isLoading } = useWorkspaceMembers();
  const [newOwnerId, setNewOwnerId] = useState<string>('');
  const [reason, setReason] = useState('');
  const { reassign, isPending, error } = useReassignOwner(workItem.id);

  useEffect(() => {
    if (open) {
      setNewOwnerId('');
      setReason('');
    }
  }, [open]);

  const eligible = members.filter((m) => m.id !== workItem.owner_id);
  const canConfirm = newOwnerId !== '' && !isPending;

  async function handleConfirm() {
    if (!canConfirm) return;
    const trimmedReason = reason.trim();
    const updated = await reassign(
      newOwnerId,
      trimmedReason === '' ? undefined : trimmedReason,
    );
    if (updated) {
      onReassigned(updated);
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
            <Label htmlFor="reassign-new-owner">{t('newOwnerLabel')}</Label>
            <Select value={newOwnerId} onValueChange={setNewOwnerId}>
              <SelectTrigger id="reassign-new-owner" aria-label={t('newOwnerLabel')}>
                <SelectValue placeholder={isLoading ? t('loading') : t('newOwnerPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                {eligible.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.full_name} ({m.email})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="reassign-reason">{t('reasonLabel')}</Label>
            <Textarea
              id="reassign-reason"
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
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
            {tCommon('cancel')}
          </Button>
          <Button type="button" onClick={() => void handleConfirm()} disabled={!canConfirm}>
            {isPending ? tCommon('saving') : t('confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
