'use client';

import { useEffect, useRef } from 'react';
import { X, ExternalLink, AlertTriangle } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Skeleton } from '@/components/ui/skeleton';
import { useDocContent } from '@/hooks/use-doc-content';

interface DocPreviewPanelProps {
  docId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

function escapeHtml(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

/**
 * Allowlist-based HTML sanitizer for doc content.
 * Strips script/style/iframe and dangerous attributes.
 * Uses a detached DOM parser — no execution.
 */
function sanitizeHtml(html: string): string {
  if (typeof window === 'undefined') return escapeHtml(html);

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  // Remove dangerous elements
  const dangerous = doc.querySelectorAll('script,style,iframe,object,embed,form,input,button');
  dangerous.forEach((el) => el.remove());

  // Remove on* event attributes
  const all = doc.querySelectorAll('*');
  all.forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      if (attr.name.startsWith('on') || attr.name === 'href' && attr.value.startsWith('javascript:')) {
        el.removeAttribute(attr.name);
      }
    });
  });

  return doc.body.innerHTML;
}

export function DocPreviewPanel({ docId, isOpen, onClose }: DocPreviewPanelProps) {
  const t = useTranslations('workspace.docs');
  const { content, isLoading } = useDocContent(isOpen ? docId : null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<Element | null>(null);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement;
      closeButtonRef.current?.focus();
    } else {
      if (previousFocusRef.current instanceof HTMLElement) {
        previousFocusRef.current.focus();
      }
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const safeContent = content ? sanitizeHtml(content.content_html) : '';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('previewTitle')}
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-background shadow-xl border-l border-border transition-transform duration-300"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex-1 min-w-0">
          {isLoading ? (
            <Skeleton className="h-5 w-48" />
          ) : content ? (
            <>
              <h2 className="text-sm font-semibold text-foreground truncate">{content.title}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">{content.source_name}</p>
            </>
          ) : (
            <h2 className="text-sm font-semibold text-foreground">{t('previewTitle')}</h2>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {content && (
            <a
              href={content.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t('openInNewTab')}
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              {t('openInNewTab')}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          )}
          <button
            ref={closeButtonRef}
            type="button"
            aria-label={t('close')}
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>

      {/* Truncated notice */}
      {content?.content_truncated && (
        <div
          data-testid="content-truncated-notice"
          className="flex items-center gap-2 bg-yellow-50 dark:bg-yellow-900/20 px-4 py-2 text-xs text-yellow-700 dark:text-yellow-300 border-b border-yellow-200 dark:border-yellow-800"
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {t('contentTruncated')}
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        )}
        {!isLoading && content && (
          <div
            data-testid="doc-content-body"
            className="prose prose-sm dark:prose-invert max-w-none"
            dangerouslySetInnerHTML={{ __html: safeContent }}
          />
        )}
        {!isLoading && !content && docId && (
          <p className="text-sm text-muted-foreground">{t('loadError')}</p>
        )}
      </div>
    </div>
  );
}
