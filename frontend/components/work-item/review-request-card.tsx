'use client';

import { useTranslations } from 'next-intl';
import { AlertTriangle, CheckCircle2, XCircle, Clock, AlertOctagon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/domain/relative-time';
import { cn } from '@/lib/utils';
import type { ReviewRequestWithResponses, ReviewDecision, ReviewRequestStatus } from '@/lib/api/reviews';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ReviewRequestCardProps {
  request: ReviewRequestWithResponses;
  currentUserId: string;
  onCancel: (id: string) => void;
  onRespond: (request: ReviewRequestWithResponses) => void;
}

// ─── Decision chip ────────────────────────────────────────────────────────────

const DECISION_CONFIG: Record<ReviewDecision, { label: string; className: string }> = {
  approved: {
    label: 'workspace.itemDetail.reviews.decision.approved',
    className: 'bg-green-500/20 text-green-700 dark:text-green-400',
  },
  changes_requested: {
    label: 'workspace.itemDetail.reviews.decision.changes_requested',
    className: 'bg-amber-500/20 text-amber-700 dark:text-amber-400',
  },
  rejected: {
    label: 'workspace.itemDetail.reviews.decision.rejected',
    className: 'bg-destructive/20 text-destructive',
  },
};

const STATUS_ICON: Record<ReviewRequestStatus, React.ReactNode> = {
  pending: <Clock className="h-3 w-3" aria-hidden />,
  closed: <CheckCircle2 className="h-3 w-3" aria-hidden />,
  cancelled: <XCircle className="h-3 w-3" aria-hidden />,
};

// ─── Component ───────────────────────────────────────────────────────────────

export function ReviewRequestCard({
  request,
  currentUserId,
  onCancel,
  onRespond,
}: ReviewRequestCardProps) {
  const t = useTranslations('workspace.itemDetail.reviews');

  const isRequester = currentUserId === request.requested_by;
  const isReviewer =
    request.reviewer_type === 'user' && request.reviewer_id === currentUserId;
  const isPending = request.status === 'pending';
  const latestResponse = request.responses[request.responses.length - 1] ?? null;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      {/* Outdated banner */}
      {request.version_outdated && (
        <div
          data-testid="outdated-banner"
          className="flex items-center gap-2 bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-sm text-amber-700 dark:text-amber-400"
        >
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
          <span>
            {t('outdatedBanner', {
              requested: request.requested_version,
              current: request.current_version,
            })}
          </span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="flex-1 text-sm font-medium text-foreground truncate">
          {request.reviewer_id ?? request.team_id ?? '—'}
        </span>

        {/* Status badge */}
        <span
          data-testid="review-status-badge"
          data-status={request.status}
          className={cn(
            'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium shrink-0',
            isPending && 'bg-muted text-muted-foreground',
            request.status === 'closed' && 'bg-green-500/20 text-green-700 dark:text-green-400',
            request.status === 'cancelled' && 'bg-muted text-muted-foreground',
          )}
        >
          {STATUS_ICON[request.status]}
          {t(`status.${request.status}`)}
        </span>

        <RelativeTime iso={request.requested_at} className="text-xs text-muted-foreground shrink-0" />
      </div>

      {/* Response decision chip (closed with response) */}
      {request.status === 'closed' && latestResponse && (
        <div className="border-t border-border px-4 py-2 flex items-center gap-2 bg-muted/20">
          <span
            data-testid="decision-chip"
            data-decision={latestResponse.decision}
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              DECISION_CONFIG[latestResponse.decision].className,
            )}
          >
            {t(`respondDialog.${latestResponse.decision === 'approved' ? 'approved' : latestResponse.decision === 'rejected' ? 'rejected' : 'changesRequested'}`)}
          </span>
          {latestResponse.content && (
            <p className="text-sm text-foreground">{latestResponse.content}</p>
          )}
          <RelativeTime iso={latestResponse.responded_at} className="ml-auto text-xs text-muted-foreground" />
        </div>
      )}

      {/* Actions */}
      {isPending && (isRequester || isReviewer) && (
        <div className="border-t border-border px-4 py-2 flex items-center gap-2 bg-muted/10">
          {isRequester && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="cancel-btn"
              onClick={() => onCancel(request.id)}
              className="text-muted-foreground text-xs"
            >
              {t('cancelButton')}
            </Button>
          )}
          {isReviewer && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="respond-btn"
              onClick={() => onRespond(request)}
              className="ml-auto text-xs"
            >
              {t('respondButton')}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
