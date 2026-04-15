'use client';

import { useState } from 'react';

interface UseCopyToClipboardReturn {
  copied: boolean;
  error: Error | null;
  copy: (text: string) => Promise<void>;
}

export function useCopyToClipboard(resetMs = 2000): UseCopyToClipboardReturn {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function copy(text: string) {
    setError(null);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), resetMs);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  return { copied, error, copy };
}
