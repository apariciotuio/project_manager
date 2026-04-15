import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TierBadge } from '@/components/domain/tier-badge';

describe('TierBadge', () => {
  it('renders tier 1', () => {
    render(<TierBadge tier={1} />);
    expect(screen.getByText('P1')).toBeTruthy();
  });

  it('renders tier 2', () => {
    render(<TierBadge tier={2} />);
    expect(screen.getByText('P2')).toBeTruthy();
  });

  it('renders tier 3', () => {
    render(<TierBadge tier={3} />);
    expect(screen.getByText('P3')).toBeTruthy();
  });

  it('renders tier 4', () => {
    render(<TierBadge tier={4} />);
    expect(screen.getByText('P4')).toBeTruthy();
  });

  it('has accessible label', () => {
    render(<TierBadge tier={1} />);
    const badge = screen.getByRole('img', { hidden: true });
    expect(badge.getAttribute('aria-label')).toContain('Prioridad 1');
  });
});
