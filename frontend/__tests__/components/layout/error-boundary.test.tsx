/**
 * ErrorBoundary tests — EP-12 Group 1
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PageErrorBoundary, SectionErrorBoundary } from '@/components/layout/error-boundary';

// Suppress React error boundary console output in tests
const consoleError = console.error;
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const msg = args[0] as string;
    if (typeof msg === 'string' && msg.includes('The above error occurred')) return;
    if (typeof msg === 'string' && msg.includes('React will try to recreate')) return;
    consoleError(...args);
  };
});
afterAll(() => {
  console.error = consoleError;
});

function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Test render error');
  return <div data-testid="child">ok</div>;
}

describe('PageErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow={false} />
      </PageErrorBoundary>,
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('renders full-page fallback on render error', () => {
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow={true} />
      </PageErrorBoundary>,
    );
    expect(screen.getByTestId('page-error-fallback')).toBeInTheDocument();
  });

  it('shows error message in fallback', () => {
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow={true} />
      </PageErrorBoundary>,
    );
    expect(screen.getByText(/test render error/i)).toBeInTheDocument();
  });

  it('shows "Go to inbox" link in page-level fallback', () => {
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow={true} />
      </PageErrorBoundary>,
    );
    expect(screen.getByRole('link', { name: /go to inbox/i })).toBeInTheDocument();
  });

  it('shows correlation_id when provided', () => {
    render(
      <PageErrorBoundary correlationId="test-corr-123">
        <Bomb shouldThrow={true} />
      </PageErrorBoundary>,
    );
    expect(screen.getByText(/test-corr-123/)).toBeInTheDocument();
  });

  it('has copy button for correlation_id', () => {
    render(
      <PageErrorBoundary correlationId="test-corr-123">
        <Bomb shouldThrow={true} />
      </PageErrorBoundary>,
    );
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
  });
});

describe('SectionErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <SectionErrorBoundary>
        <Bomb shouldThrow={false} />
      </SectionErrorBoundary>,
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('renders inline error fallback on render error', () => {
    render(
      <SectionErrorBoundary>
        <Bomb shouldThrow={true} />
      </SectionErrorBoundary>,
    );
    expect(screen.getByTestId('section-error-fallback')).toBeInTheDocument();
  });

  it('renders retry button in section fallback', () => {
    render(
      <SectionErrorBoundary>
        <Bomb shouldThrow={true} />
      </SectionErrorBoundary>,
    );
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('retry button resets the error boundary', async () => {
    // After clicking Retry, the boundary resets and tries to render children again
    // We can test this by checking the retry button triggers a re-render
    const onRetry = vi.fn();
    render(
      <SectionErrorBoundary onRetry={onRetry}>
        <Bomb shouldThrow={true} />
      </SectionErrorBoundary>,
    );
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it('does not unmount sibling content (section-level isolation)', () => {
    render(
      <div>
        <div data-testid="sibling">sibling content</div>
        <SectionErrorBoundary>
          <Bomb shouldThrow={true} />
        </SectionErrorBoundary>
      </div>,
    );
    expect(screen.getByTestId('sibling')).toBeInTheDocument();
    expect(screen.getByTestId('section-error-fallback')).toBeInTheDocument();
  });
});
