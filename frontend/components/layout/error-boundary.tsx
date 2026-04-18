'use client';

import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  correlationId?: string;
  onRetry?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

// --- Page-level ErrorBoundary ---

export class PageErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log to console only — no Sentry (resolution #27)
    console.error('[ErrorBoundary] Render error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <PageErrorFallback
          error={this.state.error}
          correlationId={this.props.correlationId}
        />
      );
    }
    return this.props.children;
  }
}

function PageErrorFallback({
  error,
  correlationId,
}: {
  error: Error | null;
  correlationId?: string;
}) {
  function handleCopy() {
    if (correlationId) {
      void navigator.clipboard.writeText(correlationId);
    }
  }

  return (
    <div
      data-testid="page-error-fallback"
      className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center"
    >
      <div className="text-destructive">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-12 w-12 mx-auto" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <div className="space-y-2">
        <h1 className="text-xl font-semibold text-foreground">Something went wrong</h1>
        <p className="text-sm text-muted-foreground max-w-md">
          {error?.message ?? 'An unexpected error occurred.'}
        </p>
      </div>
      {correlationId && (
        <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-xs font-mono text-muted-foreground">
          <span>Error reference: {correlationId}</span>
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy error reference"
            className="rounded p-1 hover:text-foreground"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3.5 w-3.5" aria-hidden="true">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
        </div>
      )}
      <a
        href="/inbox"
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Go to inbox
      </a>
    </div>
  );
}

// --- Section-level ErrorBoundary ---

interface SectionState extends State {
  retryKey: number;
}

export class SectionErrorBoundary extends Component<Props, SectionState> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, retryKey: 0 };
    this.handleRetry = this.handleRetry.bind(this);
  }

  static getDerivedStateFromError(error: Error): Partial<SectionState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[SectionErrorBoundary] Render error:', error, info.componentStack);
  }

  handleRetry() {
    this.props.onRetry?.();
    this.setState((s) => ({ hasError: false, error: null, retryKey: s.retryKey + 1 }));
  }

  render() {
    if (this.state.hasError) {
      return (
        <SectionErrorFallback
          error={this.state.error}
          correlationId={this.props.correlationId}
          onRetry={this.handleRetry}
        />
      );
    }
    return this.props.children;
  }
}

function SectionErrorFallback({
  error,
  correlationId,
  onRetry,
}: {
  error: Error | null;
  correlationId?: string;
  onRetry: () => void;
}) {
  return (
    <div
      data-testid="section-error-fallback"
      className="flex flex-col items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-center"
    >
      <p className="text-sm text-muted-foreground">
        {error?.message ?? 'Failed to load this section.'}
      </p>
      {correlationId && (
        <p className="text-xs font-mono text-muted-foreground">
          Error reference: {correlationId}
        </p>
      )}
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent transition-colors"
      >
        Retry
      </button>
    </div>
  );
}
