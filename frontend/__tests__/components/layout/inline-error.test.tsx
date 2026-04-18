import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InlineError } from '@/components/layout/inline-error';

describe('InlineError', () => {
  it('renders error message with role=alert', () => {
    render(<InlineError message="Something went wrong" />);
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders retry button when onRetry provided', () => {
    const onRetry = vi.fn();
    render(<InlineError message="Failed to load" onRetry={onRetry} />);
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('calls onRetry when retry button clicked', async () => {
    const onRetry = vi.fn();
    render(<InlineError message="Failed to load" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('omits retry button when onRetry not provided', () => {
    render(<InlineError message="Error occurred" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<InlineError message="Error" className="custom-class" />);
    expect(screen.getByRole('alert')).toHaveClass('custom-class');
  });
});
