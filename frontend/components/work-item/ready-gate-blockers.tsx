'use client';

import { useTranslations } from 'next-intl';
import { ShieldAlert } from 'lucide-react';
import { useReadyGate } from '@/hooks/work-item/use-ready-gate';

// ─── Props ────────────────────────────────────────────────────────────────────

interface ReadyGateBlockersProps {
  workItemId: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function ReadyGateBlockers({ workItemId }: ReadyGateBlockersProps) {
  const t = useTranslations('workspace.itemDetail.readyGate');
  const { gate, isLoading } = useReadyGate(workItemId);

  // Don't render anything until loaded, or if gate is clear
  if (isLoading || !gate || gate.ok || gate.blockers.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="ready-gate-blockers"
      className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2"
    >
      <div className="flex items-center gap-2 mb-1">
        <ShieldAlert className="h-4 w-4 text-destructive shrink-0" aria-hidden />
        <span className="text-xs font-semibold text-destructive">{t('blocked')}</span>
      </div>
      <ul className="flex flex-col gap-0.5 pl-6 list-disc">
        {gate.blockers.map((blocker) => (
          <li
            key={blocker.rule_id}
            data-testid={`blocker-item-${blocker.rule_id}`}
            className="text-xs text-muted-foreground"
          >
            {blocker.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
