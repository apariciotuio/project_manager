'use client';

import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

interface StickyActionBarProps {
  children: ReactNode;
  className?: string;
}

/**
 * StickyActionBar — fixed bottom bar for primary actions on mobile.
 * Renders inline (relative/static) on md+.
 * Includes pb-safe to avoid overlap with iOS home indicator.
 */
export function StickyActionBar({ children, className }: StickyActionBarProps) {
  return (
    <div
      data-testid="sticky-action-bar"
      className={cn(
        // Mobile: fixed at bottom, full width
        'fixed bottom-0 left-0 right-0 z-30',
        'bg-background border-t border-border',
        'px-4 pt-3 pb-safe',
        // Desktop: inline, not fixed
        'md:relative md:bottom-auto md:left-auto md:right-auto md:border-0 md:bg-transparent md:px-0 md:pt-0 md:pb-0',
        className,
      )}
    >
      {children}
    </div>
  );
}
