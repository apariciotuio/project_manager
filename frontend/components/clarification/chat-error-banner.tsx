'use client';

import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatErrorBannerProps {
  message: string;
  className?: string;
}

export function ChatErrorBanner({ message, className }: ChatErrorBannerProps) {
  return (
    <div
      role="alert"
      data-testid="chat-error-banner"
      className={cn(
        'flex items-start gap-2 max-w-[80%] self-start rounded-lg px-3 py-2 text-sm',
        'bg-destructive/10 text-destructive border border-destructive/20',
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
