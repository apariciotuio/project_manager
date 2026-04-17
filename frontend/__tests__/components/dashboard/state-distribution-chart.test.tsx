/**
 * EP-09 — StateDistributionChart component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StateDistributionChart } from '@/components/dashboard/state-distribution-chart';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

describe('StateDistributionChart', () => {
  it('renders the distribution bar when data has items', () => {
    render(
      <StateDistributionChart byState={{ draft: 10, in_review: 5, ready: 3 }} />,
    );
    expect(screen.getByTestId('state-distribution-bar')).toBeInTheDocument();
  });

  it('renders legend entries for each state', () => {
    render(
      <StateDistributionChart byState={{ draft: 10, in_review: 5 }} />,
    );
    expect(screen.getByText('draft')).toBeInTheDocument();
    expect(screen.getByText('in_review')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders dash when no data', () => {
    render(<StateDistributionChart byState={{}} />);
    expect(screen.queryByTestId('state-distribution-bar')).toBeNull();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('excludes zero-count states from bar', () => {
    render(
      <StateDistributionChart byState={{ draft: 10, in_review: 0, ready: 3 }} />,
    );
    // in_review has 0 — should not appear in legend
    expect(screen.queryByText('in_review')).toBeNull();
  });
});
