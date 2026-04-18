'use client';

import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { useDiffVsPrevious } from '@/hooks/work-item/use-versions';
import { cn } from '@/lib/utils';
import type { SectionDiff, DiffHunk } from '@/lib/types/versions';

// ─── Props ────────────────────────────────────────────────────────────────────

interface VersionDiffViewerProps {
  workItemId: string;
  /** When fromVersion is provided use the arbitrary diff path; otherwise use versionNumber vs previous. */
  fromVersion?: number;
  toVersion?: number;
  /** Legacy single-version mode — diff vs previous. */
  versionNumber?: number | null;
  open?: boolean;
  onClose?: () => void;
}

// ─── Hunk renderer ────────────────────────────────────────────────────────────

function HunkBlock({ hunk }: { hunk: DiffHunk }) {
  return (
    <>
      {hunk.lines.map((line, i) => (
        <span
          key={i}
          className={cn(
            'block',
            hunk.type === 'added' && 'bg-green-100 text-green-800',
            hunk.type === 'removed' && 'bg-red-100 text-red-800',
          )}
        >
          {hunk.type === 'added' ? '+ ' : hunk.type === 'removed' ? '- ' : '  '}
          {line}
        </span>
      ))}
    </>
  );
}

// ─── Section renderer ─────────────────────────────────────────────────────────

function SectionDiffBlock({ section }: { section: SectionDiff }) {
  const [expanded, setExpanded] = useState(false);

  const label = section.section_type.replace(/_/g, ' ');

  if (section.change_type === 'reordered') {
    return (
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-medium capitalize">{label}</h4>
        <span
          data-testid="reordered-badge"
          className="inline-flex items-center rounded-md bg-yellow-100 px-2 py-1 text-xs font-medium text-yellow-800"
        >
          Reordered
        </span>
      </div>
    );
  }

  if (section.change_type === 'unchanged') {
    return (
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="text-sm text-muted-foreground hover:underline text-left"
        >
          {label} — {expanded ? 'Hide unchanged' : 'Show unchanged'}
        </button>
        {expanded && (
          <pre className="text-xs font-mono rounded bg-muted p-3 overflow-x-auto whitespace-pre-wrap">
            {section.hunks.map((hunk, i) => (
              <HunkBlock key={i} hunk={hunk} />
            ))}
          </pre>
        )}
      </div>
    );
  }

  const headerColor =
    section.change_type === 'added'
      ? 'text-green-700'
      : section.change_type === 'removed'
        ? 'text-red-700'
        : '';

  return (
    <div className="flex flex-col gap-2">
      <h4 className={cn('text-sm font-medium capitalize', headerColor)}>{label}</h4>
      <pre className="text-xs font-mono rounded bg-muted p-3 overflow-x-auto whitespace-pre-wrap">
        {section.hunks.map((hunk, i) => (
          <HunkBlock key={i} hunk={hunk} />
        ))}
      </pre>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function VersionDiffViewer({
  workItemId,
  versionNumber = null,
  open,
}: VersionDiffViewerProps) {
  const t = useTranslations('workspace.itemDetail.versions');

  // For the new typed path, the parent should pass versionNumber; arbitrary diff handled via hook.
  const effectiveVersionNumber = versionNumber ?? null;
  const { diff, isLoading, error } = useDiffVsPrevious(
    workItemId,
    open !== undefined ? (open ? effectiveVersionNumber : null) : effectiveVersionNumber,
  );

  const hasChanges =
    diff !== null &&
    diff.sections.some((s) => s.change_type !== 'unchanged');

  return (
    <div className="flex flex-col gap-4 py-2">
      {isLoading && (
        <div className="flex flex-col gap-3 py-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-destructive py-4">
          {t('diffError')}
        </p>
      )}

      {diff !== null && !isLoading && !hasChanges && (
        <p className="text-sm text-muted-foreground py-4">{t('diffEmpty')}</p>
      )}

      {diff !== null && !isLoading && (
        <div className="flex flex-col gap-6">
          {diff.sections.map((section, i) => (
            <SectionDiffBlock key={i} section={section} />
          ))}
        </div>
      )}
    </div>
  );
}
