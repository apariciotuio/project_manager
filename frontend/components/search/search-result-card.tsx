'use client';

import { FileText, Bug, Lightbulb, Zap, BookOpen, MessageSquare, CheckSquare, ExternalLink } from 'lucide-react';
import type { PuppetSearchResult, SearchEntityType } from '@/lib/types/search';

interface SearchResultCardProps {
  result: PuppetSearchResult;
  slug: string;
  onClick: (result: PuppetSearchResult) => void;
}

/**
 * Strip all HTML tags from snippet — Puppet returns plain text snippets,
 * but we sanitize defensively to prevent XSS if that ever changes.
 * Uses text-only extraction so no markup survives.
 */
function sanitizeSnippet(raw: string): string {
  if (typeof window === 'undefined') {
    // SSR: strip tags via regex (no DOM)
    return raw.replace(/<[^>]*>/g, '');
  }
  const div = document.createElement('div');
  div.innerHTML = raw;
  // Remove script/style elements before extracting text to avoid leaking their content
  div.querySelectorAll('script,style').forEach((el) => el.remove());
  return div.textContent ?? '';
}

function EntityIcon({ type }: { type: SearchEntityType }) {
  const cls = 'h-4 w-4 shrink-0 text-muted-foreground';
  switch (type) {
    case 'work_item': return <FileText className={cls} aria-hidden />;
    case 'doc':       return <BookOpen className={cls} aria-hidden />;
    case 'comment':   return <MessageSquare className={cls} aria-hidden />;
    case 'task':      return <CheckSquare className={cls} aria-hidden />;
    case 'section':   return <Lightbulb className={cls} aria-hidden />;
    default:          return <Zap className={cls} aria-hidden />;
  }
}

function hrefFor(result: PuppetSearchResult, slug: string): string {
  if (result.entity_type === 'work_item') return `/workspace/${slug}/items/${result.id}`;
  return '#';
}

export function SearchResultCard({ result, slug, onClick }: SearchResultCardProps) {
  const safeSnippet = sanitizeSnippet(result.snippet);

  return (
    <li>
      <a
        href={hrefFor(result, slug)}
        className="flex items-start gap-3 px-4 py-3 hover:bg-muted/50 transition-colors"
        onClick={() => onClick(result)}
      >
        <span className="mt-0.5">
          <EntityIcon type={result.entity_type} />
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{result.title}</p>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
            {safeSnippet}
          </p>
          <div className="flex gap-1.5 mt-1 flex-wrap">
            {result.type && (
              <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-secondary text-secondary-foreground">
                {result.type}
              </span>
            )}
            {result.state && (
              <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-muted text-muted-foreground">
                {result.state}
              </span>
            )}
          </div>
        </div>
        {result.entity_type === 'doc' && (
          <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground mt-0.5" aria-hidden />
        )}
      </a>
    </li>
  );
}
