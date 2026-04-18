'use client';

import { cn } from '@/lib/utils';
import type { MorpheoPoReview } from '@/lib/types/conversation';

interface PoReviewPanelProps {
  envelope: MorpheoPoReview;
  className?: string;
}

type Verdict = 'approved' | 'needs_work' | 'rejected';
type Severity = 'low' | 'medium' | 'high' | 'critical';
type Priority = 'low' | 'medium' | 'high' | 'critical';

function verdictColor(verdict: Verdict): string {
  if (verdict === 'approved') return 'text-green-600 dark:text-green-400';
  if (verdict === 'rejected') return 'text-destructive';
  return 'text-amber-600 dark:text-amber-400';
}

function severityColor(severity: Severity): string {
  if (severity === 'critical') return 'text-destructive font-semibold';
  if (severity === 'high') return 'text-amber-600 dark:text-amber-400';
  if (severity === 'medium') return 'text-yellow-600 dark:text-yellow-400';
  return 'text-muted-foreground';
}

function priorityColor(priority: Priority): string {
  if (priority === 'critical') return 'text-destructive font-semibold';
  if (priority === 'high') return 'text-amber-600 dark:text-amber-400';
  if (priority === 'medium') return 'text-yellow-600 dark:text-yellow-400';
  return 'text-muted-foreground';
}

export function PoReviewPanel({ envelope, className }: PoReviewPanelProps) {
  const { po_review, message, comments, clarifications } = envelope;

  return (
    <div
      data-testid="po-review-panel"
      className={cn(
        'max-w-[90%] self-start rounded-lg border bg-card text-card-foreground shadow-sm text-sm space-y-3 p-3',
        className,
      )}
    >
      {/* Score header */}
      <div className="flex items-center gap-3">
        <span className={cn('text-3xl font-bold tabular-nums', verdictColor(po_review.verdict))}>
          {po_review.score}
        </span>
        <span className={cn('text-sm font-medium', verdictColor(po_review.verdict))}>
          {po_review.verdict}
        </span>
      </div>

      {/* Summary message */}
      {message && <p className="text-muted-foreground">{message}</p>}

      {/* Agents consulted */}
      {po_review.agents_consulted.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {po_review.agents_consulted.map((agent) => (
            <span
              key={agent}
              className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
            >
              {agent}
            </span>
          ))}
        </div>
      )}

      {/* Per-dimension accordion */}
      {po_review.per_dimension.length > 0 && (
        <div className="space-y-1">
          {po_review.per_dimension.map((dim) => (
            <details key={dim.dimension} className="rounded border">
              <summary
                className={cn(
                  'flex cursor-pointer items-center justify-between px-2 py-1.5 text-xs font-medium select-none',
                  verdictColor(dim.verdict),
                )}
              >
                <span>{dim.dimension}</span>
                <span className="tabular-nums">{dim.score}</span>
              </summary>
              <div className="px-2 pb-2 pt-1 space-y-1.5">
                {/* Findings */}
                {dim.findings.map((f, i) => (
                  <div key={i} className="space-y-0.5">
                    <p className={cn('text-xs', severityColor(f.severity))}>
                      [{f.severity}] {f.title}
                    </p>
                    <p className="text-xs text-muted-foreground">{f.description}</p>
                  </div>
                ))}
                {/* Missing info */}
                {dim.missing_info.length > 0 && (
                  <div className="space-y-0.5">
                    {dim.missing_info.map((m, i) => (
                      <p key={i} className="text-xs text-muted-foreground">
                        <span className="font-mono">{m.field}</span>: {m.question}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      )}

      {/* Action items */}
      {po_review.action_items.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Action items
          </p>
          {po_review.action_items.map((item, i) => (
            <div key={i} className="space-y-0.5">
              <p className={cn('text-xs', priorityColor(item.priority))}>
                [{item.priority}] {item.title}
              </p>
              <p className="text-xs text-muted-foreground">
                {item.description} — <span className="font-medium">{item.owner}</span>
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Envelope-level comments */}
      {comments && comments.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Comments
          </p>
          {comments.map((c, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              {c}
            </p>
          ))}
        </div>
      )}

      {/* Envelope-level clarifications */}
      {clarifications && clarifications.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Clarifications needed
          </p>
          {clarifications.map((cl, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              <span className="font-mono">{cl.field}</span>: {cl.question}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
