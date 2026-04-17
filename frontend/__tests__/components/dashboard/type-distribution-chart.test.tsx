/**
 * EP-09 — TypeDistributionChart component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TypeDistributionChart } from '@/components/dashboard/type-distribution-chart';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

describe('TypeDistributionChart', () => {
  it('renders distribution bar when data has items', () => {
    render(<TypeDistributionChart byType={{ bug: 5, task: 15 }} />);
    expect(screen.getByTestId('type-distribution-bar')).toBeInTheDocument();
  });

  it('renders legend entries for each type', () => {
    render(<TypeDistributionChart byType={{ bug: 5, task: 15 }} />);
    expect(screen.getByText('bug')).toBeInTheDocument();
    expect(screen.getByText('task')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  it('renders dash when empty', () => {
    render(<TypeDistributionChart byType={{}} />);
    expect(screen.queryByTestId('type-distribution-bar')).toBeNull();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('filters out zero-count types', () => {
    render(<TypeDistributionChart byType={{ bug: 0, task: 10 }} />);
    expect(screen.queryByText('bug')).toBeNull();
    expect(screen.getByText('task')).toBeInTheDocument();
  });
});
