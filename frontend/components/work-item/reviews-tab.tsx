'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ValidationsChecklist } from '@/components/work-item/validations-checklist';
import { ReviewRequestCard } from '@/components/work-item/review-request-card';
import { RequestReviewDialog } from '@/components/work-item/request-review-dialog';
import { ReviewRespondDialog } from '@/components/work-item/review-respond-dialog';
import { useReviewRequests } from '@/hooks/work-item/use-review-requests';
import type { ReviewRequest, ReviewRequestWithResponses } from '@/lib/api/reviews';

// ─── Props ────────────────────────────────────────────────────────────────────

interface ReviewsTabProps {
  workItemId: string;
  /** Real version id from useVersions; null while loading, undefined if hook not yet invoked. */
  versionId?: string | null;
  currentUserId?: string;
  isOwner?: boolean;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function ReviewsTab({ workItemId, versionId = null, currentUserId = '', isOwner = false }: ReviewsTabProps) {
  const t = useTranslations('workspace.itemDetail.reviews');

  const { requests, isLoading, error, create, cancel, refetch } = useReviewRequests(workItemId);

  const [requestDialogOpen, setRequestDialogOpen] = useState(false);
  const [respondTarget, setRespondTarget] = useState<ReviewRequestWithResponses | null>(null);

  async function handleCancel(id: string) {
    await cancel(id);
  }

  function handleRequestSuccess(_request: ReviewRequest) {
    setRequestDialogOpen(false);
    void refetch();
  }

  function handleRespondSuccess() {
    setRespondTarget(null);
    void refetch();
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Validations checklist at top */}
      <ValidationsChecklist workItemId={workItemId} isOwner={isOwner} />

      {/* Reviews section header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          {t('title', { count: requests.length })}
        </h3>
        {isOwner && (
          <Button
            size="sm"
            data-testid="request-review-btn"
            onClick={() => setRequestDialogOpen(true)}
          >
            {t('requestButton')}
          </Button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      )}

      {/* Loading */}
      {isLoading && !error ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : requests.length === 0 && !error ? (
        <p className="text-sm text-muted-foreground">{t('empty')}</p>
      ) : (
        <div className="flex flex-col gap-3">
          {requests.map((req) => (
            <ReviewRequestCard
              key={req.id}
              request={req}
              currentUserId={currentUserId}
              onCancel={(id) => void handleCancel(id)}
              onRespond={setRespondTarget}
            />
          ))}
        </div>
      )}

      {/* Request review dialog */}
      <RequestReviewDialog
        workItemId={workItemId}
        versionId={versionId}
        open={requestDialogOpen}
        onSuccess={handleRequestSuccess}
        onClose={() => setRequestDialogOpen(false)}
      />

      {/* Respond dialog */}
      {respondTarget && (
        <ReviewRespondDialog
          reviewRequestId={respondTarget.id}
          open={respondTarget !== null}
          onSuccess={handleRespondSuccess}
          onClose={() => setRespondTarget(null)}
        />
      )}
    </div>
  );
}
