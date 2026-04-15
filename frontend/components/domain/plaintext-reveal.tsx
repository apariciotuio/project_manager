'use client';

import { useState, useEffect, useRef } from 'react';
import { Eye, EyeOff, Copy, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// SECURITY: PlaintextReveal MUST NOT write value to any storage.
// Any modification that adds persistence is a security regression.

interface PlaintextRevealProps {
  /** The sensitive value to reveal. Never stored beyond component lifetime. */
  value: string;
  /** Auto-clear after N milliseconds. Default: 5 * 60 * 1000 (5 min) */
  autoClearMs?: number;
  /** Whether to show a copy button */
  showCopy?: boolean;
  /** Whether to show a download button */
  showDownload?: boolean;
  /** Filename for download */
  downloadFilename?: string;
  className?: string;
}

export function PlaintextReveal({
  value,
  autoClearMs = 5 * 60 * 1000,
  showCopy = true,
  showDownload = false,
  downloadFilename = 'clave.txt',
  className,
}: PlaintextRevealProps) {
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-clear timer
  useEffect(() => {
    if (revealed && autoClearMs > 0) {
      timerRef.current = setTimeout(() => {
        setRevealed(false);
      }, autoClearMs);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [revealed, autoClearMs]);

  // Purge on unmount
  useEffect(() => {
    return () => {
      setRevealed(false);
    };
  }, []);

  function handleReveal() {
    setRevealed(true);
  }

  function handleHide() {
    setRevealed(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable — graceful degradation
    }
  }

  function handleDownload() {
    const blob = new Blob([value], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadFilename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {revealed ? (
        <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 p-2">
          <code className="flex-1 break-all font-mono text-xs select-all">{value}</code>
          <div className="flex shrink-0 gap-1">
            {showCopy && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                aria-label={copied ? 'Copiado' : 'Copiar'}
              >
                <Copy className="h-3.5 w-3.5" aria-hidden />
                <span className="text-xs">{copied ? 'Copiado' : 'Copiar'}</span>
              </Button>
            )}
            {showDownload && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleDownload}
                aria-label="Descargar"
              >
                <Download className="h-3.5 w-3.5" aria-hidden />
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleHide}
              aria-label="Ocultar"
            >
              <EyeOff className="h-3.5 w-3.5" aria-hidden />
              <span className="text-xs">Ocultar</span>
            </Button>
          </div>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleReveal}
          aria-label="Mostrar clave"
          className="self-start"
        >
          <Eye className="h-3.5 w-3.5" aria-hidden />
          Mostrar
        </Button>
      )}
    </div>
  );
}
