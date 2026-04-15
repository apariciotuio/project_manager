import { cn } from '@/lib/utils';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import type { BadgeSize } from './state-badge';

export type Severity = 'blocking' | 'warning' | 'info';

const SEVERITY_CONFIG: Record<
  Severity,
  { label: string; icon: React.ComponentType<{ className?: string }>; className: string }
> = {
  blocking: {
    label: 'Bloqueante',
    icon: AlertCircle,
    className: 'bg-severity-blocking text-severity-blocking-foreground',
  },
  warning: {
    label: 'Aviso',
    icon: AlertTriangle,
    className: 'bg-severity-warning text-severity-warning-foreground',
  },
  info: {
    label: 'Información',
    icon: Info,
    className: 'bg-severity-info text-severity-info-foreground',
  },
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-xs gap-1 [&_svg]:h-3 [&_svg]:w-3',
  md: 'px-2 py-1 text-body-sm gap-1.5 [&_svg]:h-3.5 [&_svg]:w-3.5',
  lg: 'px-2.5 py-1.5 text-body gap-1.5 [&_svg]:h-4 [&_svg]:w-4',
};

interface SeverityBadgeProps {
  severity: Severity;
  size?: BadgeSize;
  className?: string;
}

export function SeverityBadge({ severity, size = 'md', className }: SeverityBadgeProps) {
  const config = SEVERITY_CONFIG[severity];
  const Icon = config.icon;

  return (
    <span
      role="status"
      aria-label={`Severidad: ${config.label}`}
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        config.className,
        SIZE_CLASSES[size],
        className
      )}
    >
      <Icon aria-hidden />
      {config.label}
    </span>
  );
}
