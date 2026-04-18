'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// DiffHunk — inline diff display between two text strings (line-level)
// Reuses the parseDiffLine convention from diff-viewer.tsx (EP-07).
// ---------------------------------------------------------------------------

type DiffLineType = 'add' | 'remove' | 'context';

interface DiffLine {
  text: string;
  type: DiffLineType;
}

function computeInlineDiff(current: string, proposed: string): DiffLine[] {
  const currentLines = current.split('\n');
  const proposedLines = proposed.split('\n');
  const lines: DiffLine[] = [];

  // Simple line-level diff: removed lines first, then added lines
  // For a more sophisticated LCS-diff, upgrade to a diff library later
  const maxLen = Math.max(currentLines.length, proposedLines.length);
  for (let i = 0; i < maxLen; i++) {
    const cur = currentLines[i];
    const next = proposedLines[i];
    if (cur !== undefined && next !== undefined) {
      if (cur === next) {
        lines.push({ text: cur, type: 'context' });
      } else {
        if (cur !== '') lines.push({ text: cur, type: 'remove' });
        if (next !== '') lines.push({ text: next, type: 'add' });
      }
    } else if (cur !== undefined) {
      lines.push({ text: cur, type: 'remove' });
    } else if (next !== undefined) {
      lines.push({ text: next, type: 'add' });
    }
  }

  return lines;
}

interface DiffHunkProps {
  currentContent: string;
  proposedContent: string;
}

export function DiffHunk({ currentContent, proposedContent }: DiffHunkProps) {
  const lines = computeInlineDiff(currentContent, proposedContent);
  return (
    <pre
      data-testid="diff-hunk"
      className="text-xs font-mono rounded bg-muted p-3 overflow-x-auto whitespace-pre-wrap"
    >
      {lines.map((line, i) => (
        <span
          key={i}
          className={cn(
            'block',
            line.type === 'add' && 'bg-green-100 text-green-800',
            line.type === 'remove' && 'bg-red-100 text-red-800 line-through opacity-70',
          )}
        >
          {line.type === 'add' ? '+ ' : line.type === 'remove' ? '- ' : '  '}
          {line.text}
        </span>
      ))}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// PendingSuggestionCard
// ---------------------------------------------------------------------------

export interface PendingSuggestionCardProps {
  currentContent: string;
  proposedContent: string;
  rationale: string;
  onAccept: () => void | Promise<void>;
  onReject: () => void;
  onEdit: () => void;
  /** True when the user has the textarea focused or has unsaved local edits */
  conflictMode?: boolean;
}

export function PendingSuggestionCard({
  currentContent,
  proposedContent,
  rationale,
  onAccept,
  onReject,
  onEdit,
  conflictMode = false,
}: PendingSuggestionCardProps) {
  const t = useTranslations('workspace.itemDetail.specification.suggestion');
  const [revealed, setRevealed] = useState(!conflictMode);

  // When conflictMode toggles on (user starts editing), collapse the diff
  useEffect(() => {
    if (conflictMode) {
      setRevealed(false);
    }
  }, [conflictMode]);

  const showDiff = !conflictMode || revealed;

  return (
    <div
      className="rounded-lg border border-border bg-card p-3 flex flex-col gap-2 text-sm"
      data-testid="pending-suggestion-card"
    >
      {conflictMode && (
        <div
          data-testid="conflict-banner"
          className="flex items-center justify-between gap-2 text-amber-700 bg-amber-50 rounded px-2 py-1"
        >
          <span>{t('conflictBanner')} —</span>
          {!revealed && (
            <button
              type="button"
              data-testid="reveal-proposal-btn"
              className="underline text-amber-800 hover:text-amber-900 focus-visible:ring-2 focus-visible:ring-ring rounded"
              onClick={() => setRevealed(true)}
            >
              {t('revealProposal')}
            </button>
          )}
        </div>
      )}

      {showDiff && (
        <>
          <DiffHunk currentContent={currentContent} proposedContent={proposedContent} />

          {rationale && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">{t('rationaleLabel')}: </span>
              {rationale}
            </p>
          )}

          <div className="flex gap-2 justify-end mt-1">
            <Button
              type="button"
              size="sm"
              variant="default"
              onClick={() => void onAccept()}
              aria-label={t('accept')}
            >
              {t('accept')}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onEdit}
              aria-label={t('edit')}
            >
              {t('edit')}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onReject}
              aria-label={t('reject')}
            >
              {t('reject')}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
