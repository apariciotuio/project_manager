import { cn } from '@/lib/utils';
import {
  BookOpen,
  Flag,
  Layers,
  Bug,
  CheckSquare,
  Zap,
  Lightbulb,
  RefreshCw,
  FileText,
} from 'lucide-react';
import type { BadgeSize } from './state-badge';

export type WorkitemType =
  | 'story'
  | 'milestone'
  | 'epic'
  | 'bug'
  | 'task'
  | 'spike'
  | 'idea'
  | 'change'
  | 'requirement';

const TYPE_CONFIG: Record<
  WorkitemType,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string }
> = {
  story: { label: 'Historia', icon: BookOpen, color: 'bg-primary/10 text-primary' },
  milestone: { label: 'Hito', icon: Flag, color: 'bg-warning/10 text-warning-foreground' },
  epic: { label: 'Épica', icon: Layers, color: 'bg-secondary text-secondary-foreground' },
  bug: { label: 'Error', icon: Bug, color: 'bg-destructive/10 text-destructive' },
  task: { label: 'Tarea', icon: CheckSquare, color: 'bg-info/10 text-info-foreground' },
  spike: { label: 'Investigación', icon: Zap, color: 'bg-accent text-accent-foreground' },
  idea: { label: 'Idea', icon: Lightbulb, color: 'bg-warning/10 text-warning-foreground' },
  change: { label: 'Cambio', icon: RefreshCw, color: 'bg-secondary text-secondary-foreground' },
  requirement: {
    label: 'Requisito',
    icon: FileText,
    color: 'bg-muted text-muted-foreground',
  },
};

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-xs gap-1 [&_svg]:h-3 [&_svg]:w-3',
  md: 'px-2 py-1 text-body-sm gap-1.5 [&_svg]:h-3.5 [&_svg]:w-3.5',
  lg: 'px-2.5 py-1.5 text-body gap-2 [&_svg]:h-4 [&_svg]:w-4',
};

interface TypeBadgeProps {
  type: WorkitemType;
  size?: BadgeSize;
  className?: string;
}

export function TypeBadge({ type, size = 'md', className }: TypeBadgeProps) {
  const config = TYPE_CONFIG[type];
  const Icon = config.icon;

  return (
    <span
      role="img"
      aria-label={`Tipo: ${config.label}`}
      className={cn(
        'inline-flex items-center rounded-md font-medium',
        config.color,
        SIZE_CLASSES[size],
        className
      )}
    >
      <Icon className="shrink-0" aria-hidden />
      {config.label}
    </span>
  );
}
