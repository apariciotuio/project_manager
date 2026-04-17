'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { formatRelative } from '@/hooks/use-relative-time';
import type { DraftData } from '@/hooks/use-pre-creation-draft';

interface DraftResumeBannerProps {
  pendingDraft: (DraftData & { updated_at?: string }) | null;
  onResume: () => void;
  onDiscard: () => void;
}

export function DraftResumeBanner({ pendingDraft, onResume, onDiscard }: DraftResumeBannerProps) {
  const t = useTranslations('workspace.newItem.draft');

  if (!pendingDraft) return null;

  const relativeTime = pendingDraft.updated_at ? formatRelative(pendingDraft.updated_at) : '';

  return (
    <div className="flex items-center justify-between rounded-md border border-blue-400 bg-blue-50 px-4 py-3 text-body-sm text-blue-800 dark:border-blue-600 dark:bg-blue-900/20 dark:text-blue-200">
      <div className="flex flex-col gap-0.5">
        <span className="font-medium">{t('resumeTitle')}</span>
        <span>{t('resumeBody', { time: relativeTime })}</span>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onDiscard}
        >
          {t('discardButton')}
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={onResume}
        >
          {t('resumeButton')}
        </Button>
      </div>
    </div>
  );
}
