'use client';

import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { SearchResultCard } from './search-result-card';
import { DocResultCard } from './doc-result-card';
import type { PuppetSearchResult, PuppetSearchResponse } from '@/lib/types/search';

interface SearchResultsListProps {
  response: PuppetSearchResponse | null;
  isLoading: boolean;
  error: Error | null;
  slug: string;
  onLoadMore: () => void;
  onDocPreview: (docId: string) => void;
}

export function SearchResultsList({
  response,
  isLoading,
  error,
  slug,
  onLoadMore,
  onDocPreview,
}: SearchResultsListProps) {
  const t = useTranslations('workspace.search');

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} data-testid="search-result-skeleton" className="rounded-md border border-border p-4">
            <Skeleton className="h-4 w-3/4 mb-2" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-1/2 mt-1" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        {t('unavailable')}
      </div>
    );
  }

  if (!response) return null;

  if (response.data.length === 0) {
    return (
      <div data-testid="search-empty-state" className="py-12 text-center text-muted-foreground text-sm">
        {t('empty', { query: '' })}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <ul role="list" className="rounded-md border border-border bg-card divide-y divide-border">
        {response.data.map((result: PuppetSearchResult) =>
          result.entity_type === 'doc' ? (
            <DocResultCard key={result.id} result={result} onOpenPreview={onDocPreview} />
          ) : (
            <SearchResultCard key={result.id} result={result} slug={slug} onClick={() => {}} />
          ),
        )}
      </ul>

      {response.pagination.has_next && (
        <div className="flex justify-center mt-2">
          <button
            type="button"
            aria-label={t('loadMore')}
            onClick={onLoadMore}
            className="text-sm text-primary hover:underline"
          >
            {t('loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}
