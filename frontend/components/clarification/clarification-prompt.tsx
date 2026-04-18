'use client';

import { cn } from '@/lib/utils';

interface ClarificationItem {
  field: string;
  question: string;
}

interface ClarificationPromptProps {
  message: string;
  clarifications?: ClarificationItem[];
  className?: string;
}

export function ClarificationPrompt({ message, clarifications, className }: ClarificationPromptProps) {
  return (
    <div
      data-testid="clarification-prompt"
      className={cn(
        'max-w-[85%] self-start rounded-lg px-3 py-2 text-sm bg-muted space-y-2',
        className,
      )}
    >
      <p>{message}</p>
      {clarifications && clarifications.length > 0 && (
        <ul className="space-y-1 pl-1">
          {clarifications.map((item, i) => (
            <li key={i} className="text-xs">
              <span className="font-mono text-muted-foreground">{item.field}</span>
              {': '}
              <span>{item.question}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
