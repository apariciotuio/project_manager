'use client';

import { useRelativeTime } from '@/hooks/use-relative-time';
import { cn } from '@/lib/utils';

interface RelativeTimeProps {
  iso: string;
  className?: string;
}

export function RelativeTime({ iso, className }: RelativeTimeProps) {
  const label = useRelativeTime(iso);

  return (
    <time
      dateTime={iso}
      title={new Date(iso).toLocaleString('es-ES')}
      className={cn('text-caption', className)}
    >
      {label}
    </time>
  );
}
