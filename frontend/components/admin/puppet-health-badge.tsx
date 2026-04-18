'use client';

import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import type { PuppetHealthStatus } from '@/lib/types/puppet';

interface PuppetHealthBadgeProps {
  status: PuppetHealthStatus;
}

const STATUS_VARIANTS: Record<PuppetHealthStatus, 'default' | 'destructive' | 'secondary'> = {
  ok: 'default',
  error: 'destructive',
  unchecked: 'secondary',
};

export function PuppetHealthBadge({ status }: PuppetHealthBadgeProps) {
  const t = useTranslations('workspace.admin.integrations.puppet');

  return (
    <Badge
      data-testid="puppet-health-badge"
      data-status={status}
      variant={STATUS_VARIANTS[status]}
    >
      {t(`healthStatus.${status}`)}
    </Badge>
  );
}
