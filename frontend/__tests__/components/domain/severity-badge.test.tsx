import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from '@/components/domain/severity-badge';

describe('SeverityBadge', () => {
  it('renders blocking severity', () => {
    render(<SeverityBadge severity="blocking" />);
    expect(screen.getByText('Bloqueante')).toBeTruthy();
  });

  it('renders warning severity', () => {
    render(<SeverityBadge severity="warning" />);
    expect(screen.getByText('Aviso')).toBeTruthy();
  });

  it('renders info severity', () => {
    render(<SeverityBadge severity="info" />);
    expect(screen.getByText('Información')).toBeTruthy();
  });

  it('has role status', () => {
    render(<SeverityBadge severity="blocking" />);
    expect(screen.getByRole('status')).toBeTruthy();
  });
});
