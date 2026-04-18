'use client';

/**
 * Minimal useToast hook — wraps the DOM-based toast utility.
 * Provides a React-friendly interface consistent with shadcn/ui's useToast API shape
 * so components can be tested via vi.mock('@/hooks/use-toast').
 */
import { showErrorToast } from '@/lib/errors/toast';

interface ToastOptions {
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

function showToast(opts: ToastOptions): void {
  const message = [opts.title, opts.description].filter(Boolean).join(' — ');
  if (opts.variant === 'destructive') {
    showErrorToast('TOAST', message);
    return;
  }
  if (typeof document === 'undefined') return;
  // Simple info toast rendered into the same container
  const container = document.getElementById('toast-container') ?? (() => {
    const el = document.createElement('div');
    el.id = 'toast-container';
    el.style.cssText = 'position:fixed;bottom:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:8px';
    document.body.appendChild(el);
    return el;
  })();

  const toast = document.createElement('div');
  toast.role = 'status';
  toast.setAttribute('aria-live', 'polite');
  toast.textContent = message;
  toast.style.cssText = 'background:hsl(var(--muted,0 0% 96%));color:hsl(var(--foreground,0 0% 9%));padding:12px 16px;border-radius:6px;font-size:0.875rem';
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

export function useToast() {
  return { toast: showToast };
}
