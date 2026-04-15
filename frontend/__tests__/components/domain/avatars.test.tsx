import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UserAvatar } from '@/components/domain/user-avatar';
import { OwnerAvatar } from '@/components/domain/owner-avatar';

describe('UserAvatar', () => {
  it('renders initials when no image', () => {
    render(<UserAvatar name="Ana García" />);
    // Initials fallback: AG
    expect(screen.getByText('AG')).toBeTruthy();
  });

  it('renders single initial for single-word name', () => {
    render(<UserAvatar name="Ana" />);
    expect(screen.getByText('A')).toBeTruthy();
  });

  it('has accessible aria-label', () => {
    render(<UserAvatar name="Ana García" />);
    expect(screen.getByRole('img', { name: /Ana García/ })).toBeTruthy();
  });
});

describe('OwnerAvatar', () => {
  it('renders with owner name', () => {
    render(<OwnerAvatar name="Carlos López" />);
    expect(screen.getByText('CL')).toBeTruthy();
  });

  it('shows tooltip-like title on img', () => {
    render(<OwnerAvatar name="Carlos López" />);
    const img = screen.getByRole('img');
    expect(img.getAttribute('aria-label')).toContain('Carlos López');
  });

  it('shows "Sin asignar" when no owner', () => {
    render(<OwnerAvatar />);
    const img = screen.getByRole('img');
    expect(img.getAttribute('aria-label')).toContain('Sin asignar');
  });
});
