import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CompletenessBar } from '@/components/domain/completeness-bar';

describe('CompletenessBar', () => {
  it('renders with aria-valuenow', () => {
    render(<CompletenessBar level="medium" percent={65} />);
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('65');
  });

  it('renders with aria-valuemin and aria-valuemax', () => {
    render(<CompletenessBar level="low" percent={20} />);
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuemin')).toBe('0');
    expect(bar.getAttribute('aria-valuemax')).toBe('100');
  });

  it('has accessible label', () => {
    render(<CompletenessBar level="high" percent={80} />);
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-label')).toContain('80%');
  });

  it('renders with all levels', () => {
    const levels = ['low', 'medium', 'high', 'ready'] as const;
    for (const level of levels) {
      const { container } = render(<CompletenessBar level={level} percent={50} />);
      expect(container.firstChild).toBeTruthy();
    }
  });

  it('clamps percent to 0-100', () => {
    render(<CompletenessBar level="ready" percent={150} />);
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('100');
  });
});
