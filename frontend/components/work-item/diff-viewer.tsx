'use client';

import { useTranslations } from 'next-intl';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { useDiffVsPrevious } from '@/hooks/work-item/use-versions';
import type { DiffHunk, SectionDiff } from '@/lib/types/versions';
import { cn } from '@/lib/utils';

interface DiffViewerProps {
  workItemId: string;
  versionNumber: number | null;
  open: boolean;
  onClose: () => void;
}

function metadataChanges(
  metadata: VersionMetadataDiff,
): Array<{ key: string; before: string; after: string }> {
  return Object.entries(metadata)
    .filter((entry): entry is [string, { before: string; after: string }] => entry[1] !== null)
    .map(([key, value]) => ({ key, before: value.before, after: value.after }));
}

type VersionMetadataDiff = Record<string, { before: string; after: string } | null>;

function renderHunk(hunk: DiffHunk, hunkIdx: number) {
  return (
    <pre
      key={hunkIdx}
      className="text-xs font-mono rounded bg-muted p-3 overflow-x-auto whitespace-pre-wrap"
    >
      {hunk.lines.map((line, li) => (
        <span
          key={li}
          className={cn(
            'block',
            hunk.type === 'added' && 'bg-green-100 text-green-800',
            hunk.type === 'removed' && 'bg-red-100 text-red-800 line-through opacity-70',
          )}
        >
          {hunk.type === 'added' ? '+ ' : hunk.type === 'removed' ? '- ' : '  '}
          {line}
        </span>
      ))}
    </pre>
  );
}

function SectionBlock({ section }: { section: SectionDiff }) {
  const label = section.section_type.replace(/_/g, ' ');
  if (section.change_type === 'added') {
    return (
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-medium capitalize text-green-700">+ {label}</h4>
        {section.hunks.map(renderHunk)}
      </div>
    );
  }
  if (section.change_type === 'removed') {
    return (
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-medium capitalize text-red-700">- {label}</h4>
        {section.hunks.map(renderHunk)}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <h4 className="text-sm font-medium capitalize">{label}</h4>
      {section.hunks.map(renderHunk)}
    </div>
  );
}

export function DiffViewer({ workItemId, versionNumber, open, onClose }: DiffViewerProps) {
  const t = useTranslations('workspace.itemDetail.versions');
  const { diff, isLoading, error } = useDiffVsPrevious(
    workItemId,
    open ? versionNumber : null,
  );

  const metaEntries = diff ? metadataChanges(diff.metadata_diff) : [];
  const changedSections =
    diff?.sections.filter((section) => section.change_type !== 'unchanged') ?? [];
  const hasChanges = metaEntries.length > 0 || changedSections.length > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {versionNumber !== null
              ? t('diffTitle', { version: versionNumber })
              : t('diffTitleGeneric')}
          </DialogTitle>
        </DialogHeader>

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

        {diff !== null && !isLoading && hasChanges && (
          <div className="flex flex-col gap-6 py-2">
            {metaEntries.length > 0 && (
              <div className="flex flex-col gap-2">
                <h4 className="text-sm font-medium capitalize">metadata</h4>
                <div className="grid grid-cols-[auto_1fr_1fr] gap-2 text-xs">
                  {metaEntries.map(({ key, before, after }) => (
                    <div key={key} className="contents">
                      <span className="font-mono text-muted-foreground">{key}</span>
                      <div className="rounded bg-red-50 p-2 line-through opacity-70">{before}</div>
                      <div className="rounded bg-green-50 p-2">{after}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {changedSections.map((section, i) => (
              <SectionBlock key={`${section.section_type}-${i}`} section={section} />
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
