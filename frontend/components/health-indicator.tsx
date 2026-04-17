'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { apiGet } from '@/lib/api-client';

type HealthStatus = 'ok' | 'degraded' | 'unknown';

interface HealthResponse {
  status: string;
}

const STATUS_COLORS: Record<HealthStatus, string> = {
  ok: 'bg-green-500',
  degraded: 'bg-red-500',
  unknown: 'bg-gray-400',
};

export function HealthIndicator() {
  const [status, setStatus] = useState<HealthStatus>('unknown');
  const t = useTranslations();

  useEffect(() => {
    apiGet<HealthResponse>('/api/v1/health')
      .then((data) => {
        setStatus(data.status === 'ok' ? 'ok' : 'degraded');
      })
      .catch(() => {
        setStatus('degraded');
      });
  }, []);

  const label =
    status === 'ok'
      ? t('health.ok')
      : status === 'degraded'
        ? t('health.degraded')
        : t('health.unknown');

  return (
    <div className="flex items-center gap-2" aria-label={`Health: ${label}`}>
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${STATUS_COLORS[status]}`}
        aria-hidden="true"
      />
      <span className="text-sm text-muted">{label}</span>
    </div>
  );
}
