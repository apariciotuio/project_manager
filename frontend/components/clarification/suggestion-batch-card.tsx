'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { applyBatch, generateSuggestionSet } from '@/lib/api/suggestions';
import { ApiError } from '@/lib/api-client';
import type { SuggestionSet, SuggestionItem, ApplySuggestionsResult } from '@/lib/types/suggestion';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';

interface SuggestionBatchCardProps {
  suggestionSet: SuggestionSet;
  onApplied: (result: ApplySuggestionsResult) => void;
  onDismiss: () => void;
  onRefetchSections?: () => void;
  onRefetchVersions?: () => void;
}

export function SuggestionBatchCard({
  suggestionSet,
  onApplied,
  onDismiss,
  onRefetchSections,
  onRefetchVersions,
}: SuggestionBatchCardProps) {
  const t = useTranslations('workspace.itemDetail.suggestions');
  const [expanded, setExpanded] = useState(false);
  const [localStatuses, setLocalStatuses] = useState<Record<string, 'pending' | 'accepted' | 'rejected'>>({});
  const [isApplying, setIsApplying] = useState(false);
  const [isVersionConflict, setIsVersionConflict] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const isExpired = suggestionSet.status === 'expired';

  function getStatus(item: SuggestionItem): 'pending' | 'accepted' | 'rejected' {
    return localStatuses[item.id] ?? item.status;
  }

  function toggleStatus(itemId: string, target: 'accepted' | 'rejected') {
    setLocalStatuses((prev) => ({
      ...prev,
      [itemId]: prev[itemId] === target ? 'pending' : target,
    }));
  }

  const acceptedIds = suggestionSet.items
    .filter((item) => getStatus(item) === 'accepted')
    .map((item) => item.id);

  const canApply = acceptedIds.length > 0 && !isExpired;

  async function handleApply() {
    if (!canApply || isApplying) return;
    setIsApplying(true);
    setApplyError(null);
    setIsVersionConflict(false);
    try {
      const result = await applyBatch(suggestionSet.id);
      onApplied(result);
      onRefetchSections?.();
      onRefetchVersions?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setIsVersionConflict(true);
      } else {
        setApplyError(err instanceof Error ? err.message : 'Apply failed');
      }
    } finally {
      setIsApplying(false);
    }
  }

  async function handleRegenerate() {
    setIsVersionConflict(false);
    await generateSuggestionSet(suggestionSet.work_item_id);
    onDismiss();
  }

  const statusCount = {
    accepted: acceptedIds.length,
    total: suggestionSet.items.length,
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            className="flex items-center gap-2 text-sm font-medium text-left flex-1"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={`Expand batch ${suggestionSet.id}`}
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4 shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0" />
            )}
            <span>
              {statusCount.accepted}/{statusCount.total} {t('section')}(s)
            </span>
            {isExpired && (
              <Badge variant="destructive" className="text-xs">
                {t('expired')}
              </Badge>
            )}
          </button>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              aria-label={
                acceptedIds.length > 0
                  ? t('applyAccepted', { count: acceptedIds.length })
                  : t('applySelected')
              }
              disabled={!canApply || isApplying}
              onClick={() => void handleApply()}
            >
              {isApplying ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : acceptedIds.length > 0 ? (
                t('applyAccepted', { count: acceptedIds.length })
              ) : (
                t('applySelected')
              )}
            </Button>
            <Button size="sm" variant="ghost" onClick={onDismiss}>
              ✕
            </Button>
          </div>
        </div>

        {/* Expired notice */}
        {isExpired && (
          <p className="text-xs text-muted-foreground mt-1">{t('expired')}</p>
        )}

        {/* Conflict banner */}
        {isVersionConflict && (
          <div className="mt-2 rounded-md bg-yellow-50 border border-yellow-200 px-3 py-2 text-sm">
            <p>{t('conflictBanner')}</p>
            <Button
              size="sm"
              variant="outline"
              className="mt-1"
              aria-label={t('regenerate')}
              onClick={() => void handleRegenerate()}
            >
              {t('regenerate')}
            </Button>
          </div>
        )}

        {applyError && (
          <p role="alert" className="text-xs text-destructive mt-1">{applyError}</p>
        )}
      </CardHeader>

      {expanded && (
        <CardContent className="flex flex-col gap-3 pt-0">
          {suggestionSet.items.map((item) => (
            <SuggestionDiffCard
              key={item.id}
              item={item}
              status={getStatus(item)}
              onAccept={() => toggleStatus(item.id, 'accepted')}
              onReject={() => toggleStatus(item.id, 'rejected')}
            />
          ))}
        </CardContent>
      )}
    </Card>
  );
}

interface SuggestionDiffCardProps {
  item: SuggestionItem;
  status: 'pending' | 'accepted' | 'rejected';
  onAccept: () => void;
  onReject: () => void;
}

function SuggestionDiffCard({ item, status, onAccept, onReject }: SuggestionDiffCardProps) {
  const t = useTranslations('workspace.itemDetail.suggestions');

  return (
    <div className="rounded-md border p-3 flex flex-col gap-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-xs uppercase tracking-wide text-muted-foreground">
          {item.section.replace(/_/g, ' ')}
        </span>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant={status === 'accepted' ? 'default' : 'outline'}
            className="h-6 px-2 text-xs"
            aria-label={t('accept')}
            onClick={onAccept}
          >
            {t('accept')}
          </Button>
          <Button
            size="sm"
            variant={status === 'rejected' ? 'destructive' : 'outline'}
            className="h-6 px-2 text-xs"
            aria-label={t('reject')}
            onClick={onReject}
          >
            {t('reject')}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <p className="text-xs text-muted-foreground mb-1">{t('current')}</p>
          <div className={cn('rounded p-2 bg-muted/50 text-xs whitespace-pre-wrap', status === 'accepted' && 'line-through opacity-60')}>
            {item.current_content}
          </div>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">{t('proposed')}</p>
          <div className={cn('rounded p-2 bg-green-50 text-xs whitespace-pre-wrap', status === 'accepted' && 'ring-1 ring-green-400')}>
            {item.proposed_content}
          </div>
        </div>
      </div>

      {item.rationale && (
        <p className="text-xs text-muted-foreground italic">{item.rationale}</p>
      )}
    </div>
  );
}
