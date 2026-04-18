'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Loader2 } from 'lucide-react';
import { executeQuickAction, undoQuickAction } from '@/lib/api/quick-actions';
import type { QuickActionType } from '@/lib/api/quick-actions';

export interface QuickActionMenuProps {
  workItemId: string;
  section: string;
  sectionContent: string;
  onActionApplied: (newContent: string) => void;
}

/** Actions available per section type */
function actionsForSection(section: string): QuickActionType[] {
  if (section === 'acceptance_criteria') return ['generate_ac'];
  if (section === 'description') return ['rewrite', 'concretize', 'expand', 'shorten'];
  // All other text sections
  return ['rewrite', 'expand', 'shorten'];
}

const UNDO_TIMEOUT_MS = 10_000;

export function QuickActionMenu({
  workItemId,
  section,
  sectionContent,
  onActionApplied,
}: QuickActionMenuProps) {
  const t = useTranslations('workspace.itemDetail.quickActions');
  const [isExecuting, setIsExecuting] = useState(false);
  const [undoState, setUndoState] = useState<{ actionId: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  const isEmpty = sectionContent.trim() === '';
  const actions = actionsForSection(section);

  const handleAction = useCallback(
    async (action: QuickActionType) => {
      if (isEmpty || isExecuting) return;
      setIsExecuting(true);
      setError(null);
      setUndoState(null);

      try {
        const result = await executeQuickAction(workItemId, section, action);
        if (!mounted.current) return;

        onActionApplied(result.result);
        setUndoState({ actionId: result.action_id });
        setIsExecuting(false);

        timerRef.current = setTimeout(() => {
          if (mounted.current) setUndoState(null);
        }, UNDO_TIMEOUT_MS);
      } catch (err) {
        if (!mounted.current) return;
        setIsExecuting(false);
        setError(err instanceof Error ? err.message : t('errorPrefix'));
      }
    },
    [isEmpty, isExecuting, workItemId, section, onActionApplied, t],
  );

  const handleUndo = useCallback(async () => {
    if (!undoState) return;
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    await undoQuickAction(workItemId, undoState.actionId);
    if (mounted.current) setUndoState(null);
  }, [undoState, workItemId]);

  if (isExecuting) {
    return (
      <div className="flex items-center gap-2">
        <span role="status" aria-label="executing">
          <Loader2 className="h-4 w-4 animate-spin" />
        </span>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="flex flex-wrap items-center gap-1">
        {actions.map((action) =>
          isEmpty ? (
            <Tooltip key={action}>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-xs"
                    disabled
                    aria-label={action}
                  >
                    {t(action as Parameters<typeof t>[0])}
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t('noContent')}</p>
              </TooltipContent>
            </Tooltip>
          ) : (
            <Button
              key={action}
              size="sm"
              variant="outline"
              className="h-6 px-2 text-xs"
              aria-label={action}
              onClick={() => void handleAction(action)}
            >
              {t(action as Parameters<typeof t>[0])}
            </Button>
          ),
        )}

        {/* Undo toast */}
        {undoState && (
          <Button
            size="sm"
            variant="secondary"
            className="h-6 px-2 text-xs"
            aria-label="undo"
            onClick={() => void handleUndo()}
          >
            {t('undo')}
          </Button>
        )}

        {/* Inline error */}
        {error && (
          <p role="alert" className="text-xs text-destructive">
            {error}
          </p>
        )}
      </div>
    </TooltipProvider>
  );
}
