'use client';

import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import type { DocSource, DocSourceStatus } from '@/lib/types/puppet';

interface DocSourcesTableProps {
  sources: DocSource[];
  isLoading: boolean;
  onAddSource: () => void;
  onDeleteSource: (id: string) => Promise<void>;
}

const STATUS_CLASSES: Record<DocSourceStatus, string> = {
  pending: 'bg-secondary text-secondary-foreground',
  indexing: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  indexed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  error: 'bg-destructive/10 text-destructive',
};

function StatusBadge({ source }: { source: DocSource }) {
  const t = useTranslations('workspace.admin.docSources');
  return (
    <span
      data-testid={`status-badge-${source.id}`}
      data-status={source.status}
      title={source.status === 'error' ? (source.error_message ?? undefined) : undefined}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_CLASSES[source.status]}`}
    >
      {t(`statusLabels.${source.status}`)}
    </span>
  );
}

export function DocSourcesTable({
  sources,
  isLoading,
  onAddSource,
  onDeleteSource,
}: DocSourcesTableProps) {
  const t = useTranslations('workspace.admin.docSources');
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleConfirmDelete() {
    if (!confirmingId) return;
    setDeleting(true);
    try {
      await onDeleteSource(confirmingId);
    } finally {
      setDeleting(false);
      setConfirmingId(null);
    }
  }

  if (isLoading) {
    return (
      <div data-testid="doc-sources-skeleton" className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          onClick={onAddSource}
          aria-label={t('addButton')}
        >
          {t('addButton')}
        </Button>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.name')}</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.type')}</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.url')}</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.public')}</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.status')}</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.lastIndexed')}</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t('columns.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.id} className="border-b border-border last:border-0">
                <td className="px-3 py-2 font-medium text-foreground">{source.name}</td>
                <td className="px-3 py-2 text-muted-foreground">{source.source_type}</td>
                <td className="px-3 py-2 text-muted-foreground max-w-xs truncate" title={source.url}>
                  {source.url}
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {source.is_public ? t('yes') : t('no')}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge source={source} />
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {source.last_indexed_at
                    ? new Date(source.last_indexed_at).toLocaleDateString()
                    : '—'}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    aria-label={t('deleteAria')}
                    onClick={() => setConfirmingId(source.id)}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </button>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                  {t('empty')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={confirmingId !== null} onOpenChange={(o) => { if (!o) setConfirmingId(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('confirmDeleteTitle')}</DialogTitle>
            <DialogDescription>{t('confirmDeleteMessage')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmingId(null)}>
              {t('cancelDelete')}
            </Button>
            <Button
              variant="destructive"
              disabled={deleting}
              onClick={() => void handleConfirmDelete()}
            >
              {t('confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
