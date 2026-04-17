'use client';

import { useEffect, useState } from 'react';
import { Pill } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { getPreviousTheme } from '@/lib/theme/trinity';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface BluePillProps {
  className?: string;
}

export function BluePill({ className }: BluePillProps) {
  const { theme, setTheme } = useTheme();
  const t = useTranslations('theme');
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Only render in matrix mode once the client knows the resolved theme.
  if (!mounted || !theme || theme !== 'matrix') return null;

  function handleClick() {
    const previous = getPreviousTheme();
    setTheme(previous);
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={t('bluePill.aria')}
            onClick={handleClick}
            className={cn(
              'inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full',
              'text-info transition-colors hover:bg-info/10',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              className
            )}
          >
            <Pill className="h-5 w-5 fill-current" aria-hidden />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{t('bluePill.tooltip')}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
