'use client';

import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface CopyButtonProps {
  text: string;
  label?: string;
  className?: string;
  size?: 'sm' | 'default' | 'lg' | 'icon';
}

export function CopyButton({ text, label, className, size = 'sm' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for insecure contexts
      const el = document.createElement('textarea');
      el.value = text;
      el.style.position = 'absolute';
      el.style.left = '-9999px';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size={size}
      onClick={handleCopy}
      aria-label={copied ? 'Copiado' : (label ?? 'Copiar')}
      className={cn('gap-1.5', className)}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-success" aria-hidden />
      ) : (
        <Copy className="h-3.5 w-3.5" aria-hidden />
      )}
      <span>{copied ? 'Copiado' : (label ?? 'Copiar')}</span>
    </Button>
  );
}
