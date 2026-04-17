'use client';

import { useEffect, useState } from 'react';
import { Waves } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { isRainEnabled, setRainEnabled } from '@/lib/theme/trinity';

interface RainToggleProps {
  className?: string;
}

export function RainToggle({ className }: RainToggleProps) {
  const { theme } = useTheme();
  const t = useTranslations('theme');
  const [enabled, setEnabled] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Sync from localStorage on mount
  useEffect(() => {
    setEnabled(isRainEnabled());
    setMounted(true);
  }, []);

  if (!mounted || theme !== 'matrix') return null;

  function handleToggle() {
    const next = !enabled;
    setEnabled(next);
    setRainEnabled(next);
  }

  return (
    <button
      type="button"
      aria-pressed={enabled}
      aria-label={enabled ? t('rain.off') : t('rain.on')}
      onClick={handleToggle}
      className={cn(
        'inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md',
        'text-foreground transition-colors hover:bg-accent',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        enabled && 'text-primary',
        className
      )}
      title={t('rain.toggle')}
    >
      <Waves className="h-4 w-4" aria-hidden />
    </button>
  );
}
