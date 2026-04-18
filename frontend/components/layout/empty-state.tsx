import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

type EmptyStateVariant = 'inbox-empty' | 'search-no-results' | 'filtered-no-results' | 'no-access' | 'custom';

interface EmptyStateProps {
  variant?: EmptyStateVariant;
  icon?: ReactNode;
  heading?: string;
  body?: string;
  cta?: ReactNode;
  className?: string;
}

const VARIANT_DEFAULTS: Record<Exclude<EmptyStateVariant, 'custom'>, { heading: string; body: string }> = {
  'inbox-empty': {
    heading: "You're all caught up",
    body: 'No pending items. You\'re up to date.',
  },
  'search-no-results': {
    heading: 'No results found',
    body: 'Try different keywords or check your spelling.',
  },
  'filtered-no-results': {
    heading: 'No elements match the current filters',
    body: 'Try adjusting or clearing your filters.',
  },
  'no-access': {
    heading: 'Access restricted',
    body: "You don't have access to view items here.",
  },
};

export function EmptyState({
  variant = 'custom',
  icon,
  heading,
  body,
  cta,
  className,
}: EmptyStateProps) {
  const defaults = variant !== 'custom' ? VARIANT_DEFAULTS[variant] : undefined;
  const resolvedHeading = heading ?? defaults?.heading ?? '';
  const resolvedBody = body ?? defaults?.body ?? '';

  return (
    <div
      data-testid="empty-state"
      className={cn('flex flex-col items-center gap-4 py-12 text-center', className)}
    >
      {icon && (
        <div className="text-muted-foreground" aria-hidden="true">
          {icon}
        </div>
      )}
      {resolvedHeading && (
        <h3 className="text-base font-semibold text-foreground">{resolvedHeading}</h3>
      )}
      {resolvedBody && (
        <p className="max-w-sm text-sm text-muted-foreground">{resolvedBody}</p>
      )}
      {cta && <div>{cta}</div>}
    </div>
  );
}
