import { cn } from '@/lib/utils';
import {
  FileEdit,
  Eye,
  CheckCircle2,
  ShieldAlert,
  Archive,
  Upload,
} from 'lucide-react';

export type WorkitemState = 'draft' | 'in-review' | 'ready' | 'blocked' | 'archived' | 'exported';
export type BadgeSize = 'sm' | 'md' | 'lg';

const STATE_CONFIG: Record<
  WorkitemState,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    className: string;
  }
> = {
  draft: {
    label: 'Borrador',
    icon: FileEdit,
    className: 'bg-state-draft text-state-draft-foreground',
  },
  'in-review': {
    label: 'En revisión',
    icon: Eye,
    className: 'bg-state-in-review text-state-in-review-foreground',
  },
  ready: {
    label: 'Listo',
    icon: CheckCircle2,
    className: 'bg-state-ready text-state-ready-foreground',
  },
  blocked: {
    label: 'Bloqueado',
    icon: ShieldAlert,
    className: 'bg-state-blocked text-state-blocked-foreground',
  },
  archived: {
    label: 'Archivado',
    icon: Archive,
    className: 'bg-state-archived text-state-archived-foreground',
  },
  exported: {
    label: 'Exportado',
    icon: Upload,
    className: 'bg-state-exported text-state-exported-foreground',
  },
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-xs gap-1 [&_svg]:h-3 [&_svg]:w-3',
  md: 'px-2 py-1 text-body-sm gap-1.5 [&_svg]:h-3.5 [&_svg]:w-3.5',
  lg: 'px-2.5 py-1.5 text-body gap-1.5 [&_svg]:h-4 [&_svg]:w-4',
};

interface StateBadgeProps {
  state: WorkitemState;
  size?: BadgeSize;
  className?: string;
}

export function StateBadge({ state, size = 'md', className }: StateBadgeProps) {
  const config = STATE_CONFIG[state];
  const Icon = config.icon;

  return (
    <span
      role="status"
      aria-label={`Estado: ${config.label}`}
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
