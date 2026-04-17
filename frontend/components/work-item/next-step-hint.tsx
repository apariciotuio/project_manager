'use client';

import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useNextStep } from '@/hooks/work-item/use-next-step';
import type { ValidatorSuggestion } from '@/lib/types/specification';
import { CheckCircle, AlertCircle } from 'lucide-react';

interface NextStepHintProps {
  workItemId: string;
}

function ValidatorRow({ validator }: { validator: ValidatorSuggestion }) {
  const t = useTranslations('workspace.itemDetail.nextStep');

  return (
    <div className="flex flex-col gap-0.5 py-1">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium">{validator.role}</span>
        {validator.configured ? (
          <span className="flex items-center gap-1 text-xs text-success" data-testid="validator-configured">
            <CheckCircle className="h-3 w-3" />
            {t('configured')}
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-warning-foreground" data-testid="validator-not-configured">
            <AlertCircle className="h-3 w-3" />
            {t('notConfigured')}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">{validator.reason}</p>
      {!validator.configured && validator.setup_hint && (
        <p className="text-xs text-muted-foreground italic">{validator.setup_hint}</p>
      )}
    </div>
  );
}

export function NextStepHint({ workItemId }: NextStepHintProps) {
  const t = useTranslations('workspace.itemDetail.nextStep');
  const { nextStep, isLoading } = useNextStep(workItemId);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-border p-4" aria-busy="true">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    );
  }

  if (!nextStep) {
    return null;
  }

  if (nextStep.next_step === null) {
    return (
      <div className="rounded-lg border border-border p-4" data-testid="next-step-terminal">
        <p className="text-sm text-muted-foreground">{t('terminal')}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-foreground">{t('title')}</h3>
        {nextStep.blocking && (
          <Badge variant="destructive" className="text-xs" data-testid="blocking-badge">
            {t('blocking')}
          </Badge>
        )}
      </div>

      <p className="text-sm text-foreground">{nextStep.message}</p>

      {nextStep.suggested_validators.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-border pt-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {t('validatorsTitle')}
          </h4>
          {nextStep.suggested_validators.map((v) => (
            <ValidatorRow key={v.role} validator={v} />
          ))}
        </div>
      )}
    </div>
  );
}
