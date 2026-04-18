import { render, screen } from '@testing-library/react';
import { EmptyState } from '@/components/layout/empty-state';

describe('EmptyState', () => {
  it('renders custom heading and body', () => {
    render(<EmptyState heading="Nothing here" body="Add some items to get started" />);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
    expect(screen.getByText('Add some items to get started')).toBeInTheDocument();
  });

  it('inbox-empty variant renders correct default text', () => {
    render(<EmptyState variant="inbox-empty" />);
    expect(screen.getByText(/no pending items/i)).toBeInTheDocument();
  });

  it('search-no-results variant renders correct default text', () => {
    render(<EmptyState variant="search-no-results" />);
    expect(screen.getByText(/no results found/i)).toBeInTheDocument();
  });

  it('filtered-no-results variant renders correct default text and CTA slot', () => {
    render(
      <EmptyState
        variant="filtered-no-results"
        cta={<button>Clear filters</button>}
      />
    );
    expect(screen.getByText(/no elements match/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear filters/i })).toBeInTheDocument();
  });

  it('no-access variant renders access restricted text', () => {
    render(<EmptyState variant="no-access" />);
    expect(screen.getByText(/access restricted/i)).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(<EmptyState heading="Empty" icon={<svg data-testid="icon" />} />);
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('omits icon when not provided', () => {
    render(<EmptyState heading="Empty" />);
    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
  });

  it('custom props override variant defaults', () => {
    render(<EmptyState variant="inbox-empty" heading="Override heading" />);
    expect(screen.getByText('Override heading')).toBeInTheDocument();
  });
});
