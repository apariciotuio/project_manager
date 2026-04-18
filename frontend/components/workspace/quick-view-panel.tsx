'use client';

/**
 * EP-09 — QuickViewPanel
 * Right-side slide-over. Desktop only (≥768px).
 * Mobile: not rendered — card click navigates to detail page directly.
 * Reuses getWorkItem — no duplicate API client.
 */
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { X } from 'lucide-react';
import { getWorkItem } from '@/lib/api/work-items';
import { InlineError } from '@/components/layout/inline-error';
import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface QuickViewPanelProps {
  itemId: string | null;
  onClose: () => void;
}

export function QuickViewPanel({ itemId, onClose }: QuickViewPanelProps) {
  const t = useTranslations('workspace.quickView');
  const [item, setItem] = useState<WorkItemResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!itemId) return;
    let cancelled = false;
    setIsLoading(true);
    setItem(null);
    setError(null);
    void (async () => {
      try {
        const data = await getWorkItem(itemId);
        if (!cancelled) setItem(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [itemId]);

  // Keyboard: Escape closes
  useEffect(() => {
    if (!itemId) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [itemId, onClose]);

  if (!itemId) return null;

  return (
    <div
      data-testid="quick-view-panel"
      className="fixed inset-y-0 right-0 w-[400px] max-w-full z-50 flex flex-col bg-background border-l border-border shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-label={item?.title ?? t('loading')}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-medium text-muted-foreground">{t('title')}</span>
        <button
          data-testid="quick-view-close"
          type="button"
          aria-label={t('close')}
          onClick={onClose}
          className="rounded-md p-1 hover:bg-accent"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && <SkeletonLoader variant="detail" count={1} />}

        {!isLoading && error && (
          <div data-testid="quick-view-error">
            <InlineError message={t('error')} onRetry={() => setError(null)} />
          </div>
        )}

        {!isLoading && !error && item && (
          <div className="flex flex-col gap-4">
            <h2
              data-testid="quick-view-title"
              className="text-base font-semibold text-foreground"
            >
              {item.title}
            </h2>

            <div data-testid="quick-view-state" className="text-sm text-muted-foreground">
              {item.state.replace(/_/g, ' ')}
            </div>

            {item.description && (
              <p className="text-sm text-foreground line-clamp-4">{item.description}</p>
            )}

            <div data-testid="quick-view-completeness" className="flex items-center gap-2 text-sm">
              <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${item.completeness_score}%` }}
                />
              </div>
              <span className="text-muted-foreground shrink-0">{item.completeness_score}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
