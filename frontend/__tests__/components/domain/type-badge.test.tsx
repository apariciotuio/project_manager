import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TypeBadge } from '@/components/domain/type-badge';

describe('TypeBadge', () => {
  const types = [
    { type: 'story', label: 'Historia' },
    { type: 'milestone', label: 'Hito' },
    { type: 'epic', label: 'Épica' },
    { type: 'bug', label: 'Error' },
    { type: 'task', label: 'Tarea' },
    { type: 'spike', label: 'Investigación' },
    { type: 'idea', label: 'Idea' },
    { type: 'change', label: 'Cambio' },
    { type: 'requirement', label: 'Requisito' },
  ] as const;

  for (const { type, label } of types) {
    it(`renders ${type} with label ${label}`, () => {
      render(<TypeBadge type={type} />);
      expect(screen.getByText(label)).toBeTruthy();
    });
  }

  it('has role img with accessible label', () => {
    render(<TypeBadge type="story" />);
    const badge = screen.getByRole('img', { hidden: true });
    expect(badge).toBeTruthy();
  });
});
