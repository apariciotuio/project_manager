import { cn } from '@/lib/utils';
import { Tag } from 'lucide-react';

interface VersionChipProps {
  version: string;
  className?: string;
}

export function VersionChip({ version, className }: VersionChipProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground',
        className
      )}
    >
      <Tag className="h-3 w-3" aria-hidden />
      {version}
    </span>
  );
}
