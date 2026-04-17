'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { useSearch } from '@/hooks/use-search';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface SearchBarProps {
  slug: string;
  /** Called when search results are available or cleared. */
  onResults?: (results: WorkItemResponse[] | null) => void;
  /** Called when search active state changes. */
  onSearchActiveChange?: (active: boolean) => void;
}

/**
 * EP-09 — SearchBar wired to POST /api/v1/search.
 * 300ms debounce, min 2 chars. Shows results below the bar; "Clear search" resets.
 */
export function SearchBar({ slug, onResults, onSearchActiveChange }: SearchBarProps) {
  const tSearch = useTranslations('workspace.search');
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, error, isActive } = useSearch(query);

  // Notify parent on results change
  useEffect(() => {
    onResults?.(data?.items ?? null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  useEffect(() => {
    onSearchActiveChange?.(isActive);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive]);

  const handleClear = useCallback(() => {
    setQuery('');
    inputRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col gap-2 w-full">
      {/* Input row */}
      <div className="relative flex items-center">
        <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" aria-hidden />
        <input
          ref={inputRef}
          type="search"
          role="searchbox"
          aria-label={tSearch('placeholder')}
          placeholder={tSearch('placeholder')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-10 text-body-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        {query.length > 0 && (
          <button
            type="button"
            aria-label={tSearch('clearSearch')}
            onClick={handleClear}
            className="absolute right-3 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        )}
      </div>

      {/* Results area */}
      {isActive && (
        <div data-testid="search-results-panel" className="rounded-md border border-border bg-card shadow-sm">
          {isLoading && (
            <div data-testid="search-skeleton" className="space-y-2 p-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}

          {error && !isLoading && (
            <div role="alert" className="p-3 text-body-sm text-destructive">
              {tSearch('error')}
            </div>
          )}

          {data && !isLoading && !error && (
            <>
              {/* Meta line */}
              <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-body-sm text-muted-foreground">
                <span data-testid="search-count">{tSearch('resultsCount', { count: data.total })}</span>
                <span>·</span>
                <span data-testid="search-took">{tSearch('took', { ms: data.took_ms })}</span>
                <span>·</span>
                <span data-testid="search-source">{tSearch(`source.${data.source}` as `source.${typeof data.source}`)}</span>
              </div>

              {/* Result list */}
              {data.items.length === 0 ? (
                <p className="p-3 text-body-sm text-muted-foreground">
                  {tSearch('empty', { query })}
                </p>
              ) : (
                <ul role="list" aria-label="Search results" className="divide-y divide-border">
                  {data.items.map((item) => (
                    <li key={item.id}>
                      <a
                        href={`/workspace/${slug}/items/${item.id}`}
                        className="block px-3 py-2 hover:bg-muted/50 transition-colors"
                      >
                        <p className="text-body-sm font-medium text-foreground truncate">{item.title}</p>
                        <p className="text-body-sm text-muted-foreground">{item.type} · {item.state}</p>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          {!isLoading && !error && !data && (
            <p className="p-3 text-body-sm text-muted-foreground">
              {tSearch('minChars')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
