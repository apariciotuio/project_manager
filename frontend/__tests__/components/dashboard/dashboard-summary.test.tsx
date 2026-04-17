/**
 * EP-09 — DashboardSummary component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DashboardSummary } from '@/components/dashboard/dashboard-summary';
import type { DashboardWorkItems } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockData: DashboardWorkItems = {
  total: 42,
  by_state: { draft: 10, in_review: 15, ready: 17 },
  by_type: { bug: 5, task: 20, story: 17 },
  avg_completeness: 67.5,
};

describe('DashboardSummary', () => {
  it('renders total items card', () => {
    render(<DashboardSummary data={mockData} />);
    expect(screen.getByTestId('summary-total')).toBeInTheDocument();
    expect(screen.getByTestId('summary-total')).toHaveTextContent('42');
  });

  it('renders avg completeness card rounded', () => {
    render(<DashboardSummary data={mockData} />);
    expect(screen.getByTestId('summary-avg-completeness')).toBeInTheDocument();
    // 67.5 rounded = 68%
    expect(screen.getByTestId('summary-avg-completeness')).toHaveTextContent('68%');
  });

  it('renders 0 total correctly', () => {
    render(<DashboardSummary data={{ ...mockData, total: 0, avg_completeness: 0 }} />);
    expect(screen.getByTestId('summary-total')).toHaveTextContent('0');
    expect(screen.getByTestId('summary-avg-completeness')).toHaveTextContent('0%');
  });
});
