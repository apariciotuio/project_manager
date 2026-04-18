'use client';

import { BookOpen } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRelatedDocs } from '@/hooks/use-related-docs';

interface RelatedDocsWidgetProps {
  workItemId: string;
  onDocPreview: (docId: string) => void;
}

export function RelatedDocsWidget({ workItemId, onDocPreview }: RelatedDocsWidgetProps) {
  const t = useTranslations('workspace.docs');
  const { docs, isLoading } = useRelatedDocs(workItemId);

  const isEmpty = !isLoading && docs.length === 0;

  return (
    <section aria-labelledby="related-docs-heading" className="flex flex-col gap-2">
      <h3 id="related-docs-heading" className="text-sm font-semibold text-foreground">
        {t('title')}
      </h3>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-10 rounded bg-muted animate-pulse" />
          ))}
        </div>
      )}

      {isEmpty && (
        <p data-testid="no-related-docs" className="text-xs text-muted-foreground">
          {t('noRelatedDocs')}
        </p>
      )}

      {!isLoading && docs.length > 0 && (
        <ul className="flex flex-col gap-1" role="list">
          {docs.map((doc) => (
            <li key={doc.doc_id}>
              <button
                type="button"
                className="flex items-start gap-2 w-full text-left rounded-md px-2 py-1.5 text-xs hover:bg-muted/60 transition-colors"
                onClick={() => onDocPreview(doc.doc_id)}
                aria-label={t('previewDoc', { title: doc.title })}
              >
                <BookOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground mt-0.5" aria-hidden />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground truncate">{doc.title}</p>
                  <p className="text-muted-foreground truncate">{doc.snippet}</p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
