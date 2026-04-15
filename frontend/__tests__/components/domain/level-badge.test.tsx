import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LevelBadge } from '@/components/domain/level-badge';

describe('LevelBadge', () => {
  it('renders low level', () => {
    render(<LevelBadge level="low" />);
    expect(screen.getByText('Bajo')).toBeTruthy();
  });

  it('renders medium level', () => {
    render(<LevelBadge level="medium" />);
    expect(screen.getByText('Medio')).toBeTruthy();
  });

  it('renders high level', () => {
    render(<LevelBadge level="high" />);
    expect(screen.getByText('Alto')).toBeTruthy();
  });

  it('renders ready level', () => {
    render(<LevelBadge level="ready" />);
    expect(screen.getByText('Listo')).toBeTruthy();
  });
});
