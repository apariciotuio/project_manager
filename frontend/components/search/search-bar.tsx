'use client';

import { useState, useEffect, useRef, useCallback, useId } from 'react';
import { Search, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { useSearch } from '@/hooks/use-search';
import { fetchSuggest } from '@/lib/api/search';
import type { SuggestResult } from '@/lib/api/search';
import type { WorkItemResponse } from '@/lib/types/work-item';

const SUGGEST_DEBOUNCE_MS = 150;
const MAX_SUGGEST_RESULTS = 5;

interface SearchBarProps {
  slug: string;
  /** Called when search results are available or cleared. */
  onResults?: (results: WorkItemResponse[] | null) => void;
  /** Called when search active state changes. */
  onSearchActiveChange?: (active: boolean) => void;
}

/**
 * EP-09 — SearchBar wired to POST /api/v1/search.
 * EP-13 — Adds prefix type-ahead via GET /api/v1/search/suggest (150ms debounce).
 */
export function SearchBar({ slug, onResults, onSearchActiveChange }: SearchBarProps) {
  const tSearch = useTranslations('workspace.search');
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  // Suggest state
  const [suggests, setSuggests] = useState<SuggestResult[]>([]);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [suggestActiveIdx, setSuggestActiveIdx] = useState(-1);
  const [searchUnavailable, setSearchUnavailable] = useState(false);
  const suggestTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Suggest debounce
  useEffect(() => {
    if (suggestTimerRef.current !== null) clearTimeout(suggestTimerRef.current);

    if (query.length < 2) {
      setSuggests([]);
      setSuggestOpen(false);
      setSuggestActiveIdx(-1);
      return;
    }

    suggestTimerRef.current = setTimeout(() => {
      void (async () => {
        try {
          const res = await fetchSuggest(query);
          setSuggests(res.data.slice(0, MAX_SUGGEST_RESULTS));
          setSuggestOpen(res.data.length > 0);
          setSuggestActiveIdx(-1);
          setSearchUnavailable(false);
        } catch (err) {
          const status = (err as { status?: number }).status;
          if (status === 503) {
            setSearchUnavailable(true);
            setSuggests([]);
            setSuggestOpen(false);
          }
        }
      })();
    }, SUGGEST_DEBOUNCE_MS);

    return () => {
      if (suggestTimerRef.current !== null) clearTimeout(suggestTimerRef.current);
    };
  }, [query]);

  const handleClear = useCallback(() => {
    setQuery('');
    setSuggests([]);
    setSuggestOpen(false);
    setSuggestActiveIdx(-1);
    setSearchUnavailable(false);
    inputRef.current?.focus();
  }, []);

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!suggestOpen || suggests.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSuggestActiveIdx((i) => (i + 1) % suggests.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      // ArrowUp from -1 (no selection) or 0 wraps to last
      setSuggestActiveIdx((i) => (i <= 0 ? suggests.length - 1 : i - 1));
    } else if (e.key === 'Enter' && suggestActiveIdx >= 0) {
      e.preventDefault();
      const item = suggests[suggestActiveIdx];
      if (item) {
        window.location.assign(`/workspace/${slug}/items/${item.id}`);
      }
    } else if (e.key === 'Escape') {
      setSuggestOpen(false);
      setSuggestActiveIdx(-1);
    }
  }

  return (
    <div className="flex flex-col gap-2 w-full">
      {/* Search unavailable banner */}
      {searchUnavailable && (
        <div
          data-testid="search-unavailable-banner"
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-body-sm text-destructive"
        >
          {tSearch('unavailable')}
        </div>
      )}

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
          onKeyDown={handleKeyDown}
          aria-autocomplete="list"
          aria-controls={suggestOpen ? listboxId : undefined}
          aria-activedescendant={
            suggestOpen && suggestActiveIdx >= 0
              ? `suggest-opt-${suggestActiveIdx}`
              : undefined
          }
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

      {/* Suggest dropdown */}
      {suggestOpen && suggests.length > 0 && (
        <ul
          id={listboxId}
          data-testid="suggest-dropdown"
          role="listbox"
          aria-label={tSearch('suggestions')}
          className="rounded-md border border-border bg-card shadow-sm"
        >
          {suggests.map((item, idx) => (
            <li
              key={item.id}
              id={`suggest-opt-${idx}`}
              role="option"
              aria-selected={idx === suggestActiveIdx}
              className={`cursor-pointer px-3 py-2 text-body-sm transition-colors ${
                idx === suggestActiveIdx
                  ? 'bg-muted text-foreground'
                  : 'hover:bg-muted/50 text-foreground'
              }`}
              onMouseDown={(e) => {
                e.preventDefault(); // prevent blur before click
                window.location.assign(`/workspace/${slug}/items/${item.id}`);
              }}
            >
              {item.title}
            </li>
          ))}
        </ul>
      )}

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
