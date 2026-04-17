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
import { submitReviewResponse } from '@/lib/api/reviews';
import type { ReviewDecision } from '@/lib/api/reviews';

// ─── Props ────────────────────────────────────────────────────────────────────

export interface ReviewRespondDialogProps {
  reviewRequestId: string;
  open: boolean;
  onSuccess: () => void;
  onClose: () => void;
}

const DECISIONS: ReviewDecision[] = ['approved', 'changes_requested', 'rejected'];

// ─── Component ───────────────────────────────────────────────────────────────

export function ReviewRespondDialog({
  reviewRequestId,
  open,
  onSuccess,
  onClose,
}: ReviewRespondDialogProps) {
  const t = useTranslations('workspace.itemDetail.reviews.respondDialog');

  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [content, setContent] = useState('');
  const [isPending, setIsPending] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  const needsContent = decision === 'changes_requested' || decision === 'rejected';
  const canSubmit = decision !== null && (!needsContent || content.trim().length > 0);

  function reset() {
    setDecision(null);
    setContent('');
    setInlineError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function handleSubmit() {
    if (!decision) return;
    setIsPending(true);
    setInlineError(null);
    try {
      await submitReviewResponse(reviewRequestId, {
        decision,
        content: needsContent ? content.trim() : null,
      });
      reset();
      onSuccess();
    } catch (err: unknown) {
      const anyErr = err as { status?: number; message?: string };
      if (anyErr?.status === 409) {
        setInlineError(t('errorAlreadyClosed'));
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
          {/* Decision selector */}
          <div className="flex flex-col gap-1.5">
            <Label>{t('decisionLabel')}</Label>
            <div className="flex gap-2 flex-wrap">
              {DECISIONS.map((d) => (
                <Button
                  key={d}
                  type="button"
                  data-testid={`decision-${d}`}
                  variant={decision === d ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDecision(d)}
                >
                  {d === 'approved' ? t('approved') : d === 'rejected' ? t('rejected') : t('changesRequested')}
                </Button>
              ))}
            </div>
          </div>

          {/* Content textarea — shown when decision requires explanation */}
          {needsContent && (
            <div className="flex flex-col gap-1.5">
              <Label>{t('contentLabel')}</Label>
              <Textarea
                data-testid="content-textarea"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder={t('contentPlaceholder')}
                rows={3}
              />
            </div>
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
            disabled={isPending || !canSubmit}
          >
            {t('submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
