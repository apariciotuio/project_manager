'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { formatRelative } from '@/hooks/use-relative-time';

interface StalenessWarningProps {
  onOverwrite: () => void;
  onKeepMine: () => void;
  lastServerUpdate: string;
}

export function StalenessWarning({ onOverwrite, onKeepMine, lastServerUpdate }: StalenessWarningProps) {
  const t = useTranslations('workspace.newItem.conflict');
  const relativeTime = formatRelative(lastServerUpdate);

  return (
    <div className="flex items-center justify-between rounded-md border border-yellow-400 bg-yellow-50 px-4 py-3 text-body-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-900/20 dark:text-yellow-200">
      <div className="flex flex-col gap-0.5">
        <span>{t('banner')}</span>
        <span className="text-xs opacity-75">{t('lastServerUpdate', { time: relativeTime })}</span>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onKeepMine}
        >
          {t('keepMineButton')}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onOverwrite}
        >
          {t('overwriteButton')}
        </Button>
      </div>
    </div>
  );
}
