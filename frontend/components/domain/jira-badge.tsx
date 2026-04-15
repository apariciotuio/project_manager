import { cn } from '@/lib/utils';
import { ExternalLink } from 'lucide-react';

interface JiraBadgeProps {
  issueKey: string;
  href?: string;
  className?: string;
}

export function JiraBadge({ issueKey, href, className }: JiraBadgeProps) {
  const baseClass = cn(
    'inline-flex items-center gap-1 rounded border border-border bg-muted px-1.5 py-0.5',
    'font-mono text-xs text-muted-foreground',
    className
  );

  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(baseClass, 'hover:text-foreground hover:border-foreground/30 transition-colors')}
      >
        {issueKey}
        <ExternalLink className="h-3 w-3" aria-hidden />
      </a>
    );
  }

  return <span className={baseClass}>{issueKey}</span>;
}
