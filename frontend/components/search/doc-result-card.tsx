'use client';

import { BookOpen } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { PuppetSearchResult } from '@/lib/types/search';

interface DocResultCardProps {
  result: PuppetSearchResult;
  onOpenPreview: (docId: string) => void;
}

export function DocResultCard({ result, onOpenPreview }: DocResultCardProps) {
  const t = useTranslations('workspace.docs');

  return (
    <li>
      <button
        type="button"
        className="flex items-start gap-3 w-full text-left px-4 py-3 hover:bg-muted/50 transition-colors"
        onClick={() => onOpenPreview(result.id)}
        aria-label={t('previewDoc', { title: result.title })}
      >
        <span className="mt-0.5">
          <BookOpen className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-foreground truncate">{result.title}</p>
            <span
              data-testid="entity-type-badge"
              className="inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 shrink-0"
            >
              doc
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{result.snippet}</p>
        </div>
      </button>
    </li>
  );
}
