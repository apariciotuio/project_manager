import { resolveErrorMessage } from '@/hooks/use-human-error';
import { cn } from '@/lib/utils';
import { AlertCircle } from 'lucide-react';

interface HumanErrorProps {
  code: string;
  className?: string;
}

/**
 * Renders a localized, human-friendly error message.
 * SECURITY: renders text nodes only — no dangerouslySetInnerHTML.
 */
export function HumanError({ code, className }: HumanErrorProps) {
  const message = resolveErrorMessage(code);

  return (
    <div
      role="alert"
      data-error={code}
      className={cn(
        'flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-body-sm text-destructive',
        className
      )}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}
