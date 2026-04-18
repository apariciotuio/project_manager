'use client';

import { cn } from '@/lib/utils';
import Link from 'next/link';
import type { ReactNode } from 'react';

// Icon map — simple SVG icons to avoid adding an icon library dep
const ICON_MAP: Record<string, ReactNode> = {
  inbox: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5" aria-hidden="true">
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </svg>
  ),
  list: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5" aria-hidden="true">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  ),
  search: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5" aria-hidden="true">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  settings: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  home: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5" aria-hidden="true">
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
};

export type NavIconName = keyof typeof ICON_MAP;

export interface NavItem {
  href: string;
  label: string;
  icon: NavIconName;
}

interface AppShellProps {
  navItems: NavItem[];
  activeHref: string;
  children: ReactNode;
  className?: string;
}

export function AppShell({ navItems, activeHref, children, className }: AppShellProps) {
  const items = navItems.slice(0, 5);

  return (
    <div className={cn('flex h-screen', className)}>
      {/* Sidebar — visible on lg+, hidden on mobile */}
      <nav
        aria-label="Sidebar navigation"
        className="hidden lg:flex lg:flex-col lg:w-64 lg:border-r lg:border-border lg:bg-background lg:shrink-0"
      >
        <div className="flex flex-col gap-1 p-4 pt-6">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={activeHref === item.href ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                'min-h-[touch] min-w-[touch]',
                activeHref === item.href
                  ? 'bg-primary text-primary-foreground'
                  : 'text-foreground hover:bg-accent hover:text-accent-foreground',
              )}
            >
              {ICON_MAP[item.icon]}
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto pb-16 lg:pb-0">
        {children}
      </main>

      {/* Bottom nav — visible on <lg, hidden on lg+ */}
      <nav
        aria-label="Bottom navigation"
        className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around border-t border-border bg-background pb-safe lg:hidden"
      >
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={activeHref === item.href ? 'page' : undefined}
            className={cn(
              'flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs font-medium transition-colors',
              'min-h-[48px] min-w-[48px]',
              activeHref === item.href
                ? 'text-primary'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {ICON_MAP[item.icon]}
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
