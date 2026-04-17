'use client';

import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const t = useTranslations('theme');
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  function toggle() {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  }

  // Avoid hydration mismatch — resolvedTheme is undefined on server
  const Icon = mounted && resolvedTheme === 'dark' ? Sun : Moon;

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={t('toggle')}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5',
        'text-body-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-none',
        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className
      )}
    >
      <Icon className="h-4 w-4" aria-hidden />
      {t('toggle')}
    </button>
  );
}
