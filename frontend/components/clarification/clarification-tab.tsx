'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';
import { ChatPanel } from './chat-panel';
import { GapPanel } from './gap-panel';
import { SuggestionBatchCard } from './suggestion-batch-card';
import { useSuggestions, SOFT_TIMEOUT_MS } from '@/hooks/work-item/use-suggestions';
import type { ApplySuggestionsResult } from '@/lib/types/suggestion';

interface ClarificationTabProps {
  workItemId: string;
  workItemVersion: number;
  canEdit: boolean;
}

export function ClarificationTab({ workItemId, workItemVersion, canEdit }: ClarificationTabProps) {
  const t = useTranslations('workspace.itemDetail.suggestions');
  const tChat = useTranslations('workspace.itemDetail.clarification');
  const {
    suggestionSet,
    generateStatus,
    generate,
    isVersionConflict: _isVersionConflict,
  } = useSuggestions(workItemId);

  const [generateStartedAt, setGenerateStartedAt] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const elapsed = generateStartedAt ? Date.now() - generateStartedAt : 0;
  const showSoftTimeout = elapsed >= SOFT_TIMEOUT_MS;

  async function handleGenerate() {
    setGenerateStartedAt(Date.now());
    setDismissed(false);
    await generate();
  }

  function handleApplied(result: ApplySuggestionsResult) {
    void result;
    setDismissed(true);
    setGenerateStartedAt(null);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Gap panel */}
      <section>
        <GapPanel workItemId={workItemId} workItemVersion={workItemVersion} />
      </section>

      {/* Chat panel */}
      <section className="border rounded-lg overflow-hidden" style={{ minHeight: '400px' }}>
        <ChatPanel workItemId={workItemId} />
      </section>

      {/* Suggestions */}
      {canEdit && (
        <section className="flex flex-col gap-3">
          {generateStatus === 'idle' || generateStatus === 'error' ? (
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                aria-label={t('generateButton')}
                onClick={() => void handleGenerate()}
              >
                {t('generateButton')}
              </Button>
              {generateStatus === 'error' && (
                <p className="text-sm text-destructive">{t('timeoutError')}</p>
              )}
            </div>
          ) : generateStatus === 'pending' ? (
            <GeneratingProgress showSoftTimeout={showSoftTimeout} t={t} />
          ) : generateStatus === 'timeout' ? (
            <div className="flex items-center gap-3">
              <p className="text-sm text-destructive">{t('timeoutError')}</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void handleGenerate()}
              >
                {t('retryGenerate')}
              </Button>
            </div>
          ) : generateStatus === 'ready' && suggestionSet && !dismissed ? (
            <SuggestionBatchCard
              suggestionSet={suggestionSet}
              onApplied={handleApplied}
              onDismiss={() => setDismissed(true)}
            />
          ) : null}
        </section>
      )}
    </div>
  );
}

function GeneratingProgress({
  showSoftTimeout,
  t,
}: {
  showSoftTimeout: boolean;
  t: (key: string) => string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>{t('generating')}</span>
      {showSoftTimeout && (
        <span className="text-yellow-600">{t('takingLonger')}</span>
      )}
    </div>
  );
}
