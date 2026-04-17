'use client';

import { useEffect, useState } from 'react';
import { Sun, Moon, MonitorSmartphone } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

interface ThemeSwitcherProps {
  className?: string;
}

const OPTIONS = [
  { key: 'light', Icon: Sun } as const,
  { key: 'dark', Icon: Moon } as const,
  { key: 'system', Icon: MonitorSmartphone } as const,
];

export function ThemeSwitcher({ className }: ThemeSwitcherProps) {
  const { theme, setTheme } = useTheme();
  const t = useTranslations('theme');
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div
      role="group"
      aria-label={t('switcher.ariaLabel')}
      className={cn(
        'inline-flex items-center rounded-md border border-border',
        className
      )}
    >
      {OPTIONS.map(({ key, Icon }) => {
        // Before mount, no option is active to keep SSR and first client render identical.
        const isActive = mounted && theme === key;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={isActive}
            onClick={() => setTheme(key)}
            className={cn(
              // Minimum 44×44 px touch target
              'relative inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 px-3 py-2',
              'text-body-sm transition-colors',
              'first:rounded-l-md last:rounded-r-md',
              'focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2',
              'focus-visible:ring-ring focus-visible:ring-offset-1',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-foreground hover:bg-accent hover:text-accent-foreground'
            )}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            <span className="hidden sm:inline">{t(`switcher.${key}`)}</span>
          </button>
        );
      })}
    </div>
  );
}
