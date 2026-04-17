'use client';

import { useEffect, useState } from 'react';
import { Pill } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { setPreviousTheme } from '@/lib/theme/trinity';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface RedPillProps {
  className?: string;
}

export function RedPill({ className }: RedPillProps) {
  const { theme, setTheme } = useTheme();
  const t = useTranslations('theme');
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Wait until the client knows the resolved theme — avoids SSR/CSR hydration mismatch.
  if (!mounted || !theme || theme === 'matrix') return null;

  function handleClick() {
    setPreviousTheme(theme as 'light' | 'dark' | 'system');
    setTheme('matrix');
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={t('redPill.aria')}
            onClick={handleClick}
            className={cn(
              'inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full',
              'text-destructive transition-colors hover:bg-destructive/10',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              className
            )}
          >
            <Pill className="h-5 w-5 fill-current" aria-hidden />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{t('redPill.tooltip')}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
