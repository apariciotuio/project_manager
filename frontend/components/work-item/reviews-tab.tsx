'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { RelativeTime } from '@/components/domain/relative-time';
import { useReviews } from '@/hooks/work-item/use-reviews';
import type { ReviewResponse, ReviewStatus } from '@/lib/types/work-item-detail';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Clock, Ban } from 'lucide-react';

const REVIEW_STATUS_CONFIG: Record<
  ReviewStatus,
  { label: string; className: string; icon: React.ComponentType<{ className?: string }> }
> = {
  pending: { label: 'Pendiente', className: 'bg-muted text-muted-foreground', icon: Clock },
  approved: { label: 'Aprobado', className: 'bg-level-ready text-level-ready-foreground', icon: CheckCircle2 },
  changes_requested: { label: 'Cambios solicitados', className: 'bg-severity-warning text-severity-warning-foreground', icon: XCircle },
  dismissed: { label: 'Descartado', className: 'bg-muted text-muted-foreground', icon: Ban },
};

interface ReviewCardProps {
  review: ReviewResponse;
}

function ReviewCard({ review }: ReviewCardProps) {
  const [expanded, setExpanded] = useState(false);
  const cfg = REVIEW_STATUS_CONFIG[review.status];
  const Icon = cfg.icon;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden />
        )}
        <span className="flex-1 text-sm font-medium text-foreground truncate">
          {review.reviewer_name ?? review.reviewer_id}
        </span>
        <span
          className={cn(
            'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium shrink-0',
            cfg.className
          )}
          aria-label={`Estado de revisión: ${cfg.label}`}
        >
          <Icon className="h-3 w-3" aria-hidden />
          {cfg.label}
        </span>
        <RelativeTime iso={review.requested_at} className="text-xs shrink-0" />
      </button>

      {expanded && review.responses.length > 0 && (
        <div className="border-t border-border px-4 py-3 flex flex-col gap-3 bg-muted/20">
          {review.responses.map((resp) => (
            <div key={resp.id} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'text-xs px-1.5 py-0.5 rounded-full font-medium',
                    resp.decision === 'approved'
                      ? 'bg-level-ready text-level-ready-foreground'
                      : 'bg-severity-warning text-severity-warning-foreground'
                  )}
                >
                  {resp.decision === 'approved' ? 'Aprobado' : 'Cambios solicitados'}
                </span>
                <RelativeTime iso={resp.responded_at} className="text-xs" />
              </div>
              {resp.content && (
                <p className="text-sm text-foreground whitespace-pre-wrap">{resp.content}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {expanded && review.responses.length === 0 && (
        <div className="border-t border-border px-4 py-3 bg-muted/20">
          <p className="text-sm text-muted-foreground">Sin respuestas todavía.</p>
        </div>
      )}
    </div>
  );
}

interface ReviewsTabProps {
  workItemId: string;
}

export function ReviewsTab({ workItemId }: ReviewsTabProps) {
  const { reviews, isLoading, requestReview } = useReviews(workItemId);
  const [reviewerInput, setReviewerInput] = useState('');
  const [requesting, setRequesting] = useState(false);
  const [showForm, setShowForm] = useState(false);

  async function handleRequestReview(e: React.FormEvent) {
    e.preventDefault();
    if (!reviewerInput.trim()) return;
    setRequesting(true);
    try {
      await requestReview({ reviewer_id: reviewerInput.trim() });
      setReviewerInput('');
      setShowForm(false);
    } finally {
      setRequesting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Revisiones ({reviews.length})
        </h3>
        <Button
          size="sm"
          onClick={() => setShowForm((v) => !v)}
          aria-expanded={showForm}
        >
          Solicitar revisión
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={handleRequestReview}
          className="flex items-center gap-2 rounded-lg border border-border p-3 bg-muted/20"
        >
          <Input
            autoFocus
            value={reviewerInput}
            onChange={(e) => setReviewerInput(e.target.value)}
            placeholder="ID del revisor…"
            disabled={requesting}
            aria-label="ID del revisor"
            className="h-8 text-sm"
          />
          <Button type="submit" size="sm" disabled={requesting || !reviewerInput.trim()}>
            Enviar
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowForm(false);
              setReviewerInput('');
            }}
          >
            Cancelar
          </Button>
        </form>
      )}

      {isLoading ? (
        Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))
      ) : reviews.length === 0 ? (
        <p className="text-sm text-muted-foreground">No hay revisiones todavía.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {reviews.map((review) => (
            <ReviewCard key={review.id} review={review} />
          ))}
        </div>
      )}
    </div>
  );
}
