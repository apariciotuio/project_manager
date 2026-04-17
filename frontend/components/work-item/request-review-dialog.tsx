'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
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
import { createReviewRequest } from '@/lib/api/reviews';
import type { ReviewRequest } from '@/lib/api/reviews';

// ─── Props ────────────────────────────────────────────────────────────────────

export interface RequestReviewDialogProps {
  workItemId: string;
  /** Real version id from the server. If null, the item has no version yet — submit is blocked. */
  versionId?: string | null;
  open: boolean;
  onSuccess: (request: ReviewRequest) => void;
  onClose: () => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function RequestReviewDialog({
  workItemId,
  versionId = null,
  open,
  onSuccess,
  onClose,
}: RequestReviewDialogProps) {
  const t = useTranslations('workspace.itemDetail.reviews.requestDialog');
  const { members, isLoading: membersLoading } = useWorkspaceMembers();

  const [reviewerId, setReviewerId] = useState('');
  const [note, setNote] = useState('');
  const [isPending, setIsPending] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  function reset() {
    setReviewerId('');
    setNote('');
    setInlineError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function handleSubmit() {
    if (!reviewerId || !versionId) return;
    setIsPending(true);
    setInlineError(null);
    try {
      const result = await createReviewRequest(workItemId, {
        reviewer_id: reviewerId,
        version_id: versionId,
      });
      reset();
      onSuccess(result);
    } catch (err: unknown) {
      const anyErr = err as { status?: number; message?: string };
      if (anyErr?.status === 403) {
        setInlineError(t('errorForbidden'));
      } else {
        setInlineError(anyErr?.message ?? 'Error');
      }
    } finally {
      setIsPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('title')}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>{t('reviewerLabel')}</Label>
            <Select
              value={reviewerId}
              onValueChange={setReviewerId}
              disabled={membersLoading}
            >
              <SelectTrigger data-testid="reviewer-select">
                <SelectValue placeholder={t('reviewerPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                {members.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{t('noteLabel')}</Label>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('notePlaceholder')}
              rows={2}
            />
          </div>

          {versionId === null && (
            <p data-testid="version-pending-hint" className="text-sm text-muted-foreground">
              {t('versionPending')}
            </p>
          )}

          {inlineError && (
            <p role="alert" data-testid="inline-error" className="text-sm text-destructive">
              {inlineError}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            data-testid="cancel-btn"
            onClick={handleClose}
            disabled={isPending}
          >
            {t('cancel')}
          </Button>
          <Button
            type="button"
            data-testid="submit-btn"
            onClick={() => void handleSubmit()}
            disabled={isPending || !reviewerId || versionId === null}
          >
            {t('submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
