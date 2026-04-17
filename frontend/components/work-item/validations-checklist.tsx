'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { CheckCircle2, Circle, Ban, Minus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { useValidations } from '@/hooks/work-item/use-validations';
import type { ValidationRuleStatus, ValidationState } from '@/lib/api/validations';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ValidationsChecklistProps {
  workItemId: string;
  isOwner: boolean;
}

// ─── Rule row ────────────────────────────────────────────────────────────────

const STATUS_ICON: Record<ValidationState, React.ReactNode> = {
  passed: <CheckCircle2 className="h-4 w-4 text-green-500" aria-hidden />,
  pending: <Circle className="h-4 w-4 text-muted-foreground" aria-hidden />,
  waived: <Minus className="h-4 w-4 text-amber-500" aria-hidden />,
  obsolete: <Ban className="h-4 w-4 text-muted-foreground/50" aria-hidden />,
};

interface RuleRowProps {
  rule: ValidationRuleStatus;
  isOwner: boolean;
  canWaive: boolean;
  onWaive: (rule: ValidationRuleStatus) => void;
  waiveLabel: string;
}

function RuleRow({ rule, canWaive, onWaive, waiveLabel }: RuleRowProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 py-2',
        rule.status === 'obsolete' && 'opacity-40',
      )}
    >
      <span
        data-testid={`rule-status-${rule.rule_id}`}
        data-status={rule.status}
        className="shrink-0"
      >
        {STATUS_ICON[rule.status]}
      </span>
      <span className="flex-1 text-sm text-foreground">{rule.label}</span>
      {canWaive && rule.status === 'pending' && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          data-testid={`waive-btn-${rule.rule_id}`}
          onClick={() => onWaive(rule)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {waiveLabel}
        </Button>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function ValidationsChecklist({ workItemId, isOwner }: ValidationsChecklistProps) {
  const t = useTranslations('workspace.itemDetail.validations');
  const { checklist: checklistOrNull, isLoading, waive } = useValidations(workItemId);
  const checklist = checklistOrNull ?? { required: [], recommended: [] };
  const [waiveTarget, setWaiveTarget] = useState<ValidationRuleStatus | null>(null);
  const [waivedIds, setWaivedIds] = useState<Set<string>>(new Set());

  const mandatoryTotal = checklist.required.length;
  const mandatorySatisfied = checklist.required.filter(
    (r) => r.status === 'passed' || r.status === 'waived',
  ).length;
  const gateBlocked = mandatorySatisfied < mandatoryTotal;

  async function handleConfirmWaive() {
    if (!waiveTarget) return;
    setWaivedIds((prev) => new Set(prev).add(waiveTarget.rule_id));
    setWaiveTarget(null);
    await waive(waiveTarget.rule_id);
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Required section */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
          {t('requiredSection')}
        </h4>
        <div className="divide-y divide-border">
          {checklist.required.map((rule) => (
            <RuleRow
              key={rule.rule_id}
              rule={waivedIds.has(rule.rule_id) ? { ...rule, status: 'waived' } : rule}
              isOwner={isOwner}
              canWaive={false}
              onWaive={setWaiveTarget}
              waiveLabel={t('waiveButton')}
            />
          ))}
        </div>
      </div>

      {/* Recommended section */}
      {checklist.recommended.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            {t('recommendedSection')}
          </h4>
          <div className="divide-y divide-border">
            {checklist.recommended.map((rule) => (
              <RuleRow
                key={rule.rule_id}
                rule={waivedIds.has(rule.rule_id) ? { ...rule, status: 'waived' } : rule}
                isOwner={isOwner}
                canWaive={isOwner}
                onWaive={setWaiveTarget}
                waiveLabel={t('waiveButton')}
              />
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div
        data-testid="validations-footer"
        className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm"
      >
        <span className="text-muted-foreground">
          {t('mandatoryProgress', { satisfied: mandatorySatisfied, total: mandatoryTotal })}
        </span>
        <span
          data-testid="gate-chip"
          className={cn(
            'ml-auto rounded-full px-2 py-0.5 text-xs font-medium',
            gateBlocked
              ? 'bg-destructive/20 text-destructive'
              : 'bg-green-500/20 text-green-700 dark:text-green-400',
          )}
        >
          {gateBlocked ? t('gateBlocked') : t('gateUnblocked')}
        </span>
      </div>

      {/* Waive confirmation dialog */}
      <Dialog open={waiveTarget !== null} onOpenChange={(open) => { if (!open) setWaiveTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('waiveConfirmTitle')}</DialogTitle>
            <DialogDescription>
              {t('waiveConfirmDescription', { label: waiveTarget?.label ?? '' })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWaiveTarget(null)}>
              {/* cancel label via common */}
              Cancel
            </Button>
            <Button onClick={() => void handleConfirmWaive()}>
              {t('waiveConfirmButton')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
