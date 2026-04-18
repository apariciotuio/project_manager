import { cn } from '@/lib/utils';

interface InlineErrorProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function InlineError({ message, onRetry, className }: InlineErrorProps) {
  return (
    <div
      role="alert"
      className={cn('flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive', className)}
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4 shrink-0" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 text-xs font-medium underline-offset-2 hover:underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}
