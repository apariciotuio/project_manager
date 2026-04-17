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
import { cn } from '@/lib/utils';

interface DiffViewerProps {
  workItemId: string;
  versionNumber: number | null;
  open: boolean;
  onClose: () => void;
}

interface DiffLine {
  line: string;
  type: 'add' | 'remove' | 'context';
}

function parseDiffLine(line: string): DiffLine {
  if (line.startsWith('+')) return { line: line.slice(1), type: 'add' };
  if (line.startsWith('-')) return { line: line.slice(1), type: 'remove' };
  return { line, type: 'context' };
}

export function DiffViewer({ workItemId, versionNumber, open, onClose }: DiffViewerProps) {
  const t = useTranslations('workspace.itemDetail.versions');
  const { diff, isLoading, error } = useDiffVsPrevious(
    workItemId,
    open ? versionNumber : null,
  );

  const hasChanges =
    diff !== null &&
    (diff.sections_changed.length > 0 ||
      diff.sections_added.length > 0 ||
      diff.sections_removed.length > 0 ||
      diff.work_item_changed ||
      diff.task_nodes_changed);

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
            {/* Changed sections */}
            {(diff.sections_changed as SectionChangedEntry[]).map((sc, i) => (
              <div key={i} className="flex flex-col gap-2">
                <h4 className="text-sm font-medium capitalize">
                  {sc.section_type?.replace(/_/g, ' ')}
                </h4>
                {Array.isArray(sc.diff_lines) ? (
                  <pre className="text-xs font-mono rounded bg-muted p-3 overflow-x-auto whitespace-pre-wrap">
                    {sc.diff_lines.map((line: string, li: number) => {
                      const { line: text, type } = parseDiffLine(line);
                      return (
                        <span
                          key={li}
                          className={cn(
                            'block',
                            type === 'add' && 'bg-green-100 text-green-800',
                            type === 'remove' && 'bg-red-100 text-red-800 line-through opacity-70',
                          )}
                        >
                          {type === 'add' ? '+ ' : type === 'remove' ? '- ' : '  '}
                          {text}
                        </span>
                      );
                    })}
                  </pre>
                ) : (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded bg-red-50 p-2 line-through opacity-70">{sc.from as string}</div>
                    <div className="rounded bg-green-50 p-2">{sc.to as string}</div>
                  </div>
                )}
              </div>
            ))}

            {/* Added sections */}
            {(diff.sections_added as SectionAddedEntry[]).map((sa, i) => (
              <div key={i} className="flex flex-col gap-2">
                <h4 className="text-sm font-medium capitalize text-green-700">
                  + {sa.section_type?.replace(/_/g, ' ')}
                </h4>
                <pre className="text-xs font-mono rounded bg-green-50 p-3 whitespace-pre-wrap">
                  {sa.content as string}
                </pre>
              </div>
            ))}

            {/* Removed sections */}
            {(diff.sections_removed as SectionRemovedEntry[]).map((sr, i) => (
              <div key={i} className="flex flex-col gap-2">
                <h4 className="text-sm font-medium capitalize text-red-700">
                  - {sr.section_type?.replace(/_/g, ' ')}
                </h4>
                <pre className="text-xs font-mono rounded bg-red-50 p-3 whitespace-pre-wrap line-through opacity-70">
                  {sr.content as string}
                </pre>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// Loose types for the diff payload coming from the backend
interface SectionChangedEntry {
  section_type?: string;
  from?: unknown;
  to?: unknown;
  diff_lines?: string[];
}
interface SectionAddedEntry {
  section_type?: string;
  content?: unknown;
}
interface SectionRemovedEntry {
  section_type?: string;
  content?: unknown;
}
