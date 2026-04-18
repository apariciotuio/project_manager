import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatErrorBanner } from '@/components/clarification/chat-error-banner';

describe('ChatErrorBanner', () => {
  it('renders the message text', () => {
    render(<ChatErrorBanner message="synthesis_failed" />);
    expect(screen.getByText('synthesis_failed')).toBeInTheDocument();
  });

  it('renders malformed_response message', () => {
    render(<ChatErrorBanner message="malformed_response" />);
    expect(screen.getByText('malformed_response')).toBeInTheDocument();
  });

  it('has data-testid for targeting', () => {
    render(<ChatErrorBanner message="some_error" />);
    expect(screen.getByTestId('chat-error-banner')).toBeInTheDocument();
  });

  it('has role=alert for a11y', () => {
    render(<ChatErrorBanner message="some_error" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('does not render as a toast / outside transcript flow', () => {
    const { container } = render(<ChatErrorBanner message="err" />);
    // Should be inline (div, not a portal)
    expect(container.firstChild).not.toBeNull();
  });
});
