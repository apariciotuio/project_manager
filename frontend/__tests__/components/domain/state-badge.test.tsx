import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StateBadge } from '@/components/domain/state-badge';

describe('StateBadge', () => {
  it('renders draft state with correct label', () => {
    render(<StateBadge state="draft" />);
    expect(screen.getByText('Borrador')).toBeTruthy();
  });

  it('renders ready state', () => {
    render(<StateBadge state="ready" />);
    expect(screen.getByText('Listo')).toBeTruthy();
  });

  it('renders blocked state', () => {
    render(<StateBadge state="blocked" />);
    expect(screen.getByText('Bloqueado')).toBeTruthy();
  });

  it('renders in-review state', () => {
    render(<StateBadge state="in-review" />);
    expect(screen.getByText('En revisión')).toBeTruthy();
  });

  it('renders archived state', () => {
    render(<StateBadge state="archived" />);
    expect(screen.getByText('Archivado')).toBeTruthy();
  });

  it('renders exported state', () => {
    render(<StateBadge state="exported" />);
    expect(screen.getByText('Exportado')).toBeTruthy();
  });

  it('has accessible aria-label', () => {
    render(<StateBadge state="ready" />);
    const badge = screen.getByRole('status');
    expect(badge).toBeTruthy();
    expect(badge.getAttribute('aria-label')).toBe('Estado: Listo');
  });

  it('accepts size prop', () => {
    const { container } = render(<StateBadge state="draft" size="sm" />);
    expect(container.firstChild).toBeTruthy();
  });
});
