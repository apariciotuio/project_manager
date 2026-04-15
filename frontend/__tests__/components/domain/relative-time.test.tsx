import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RelativeTime } from '@/components/domain/relative-time';

describe('RelativeTime', () => {
  it('renders a time element', () => {
    const iso = new Date(Date.now() - 60_000).toISOString();
    render(<RelativeTime iso={iso} />);
    expect(screen.getByRole('time')).toBeTruthy();
  });

  it('has datetime attribute with the ISO string', () => {
    const iso = '2026-01-01T12:00:00.000Z';
    render(<RelativeTime iso={iso} />);
    const el = screen.getByRole('time');
    expect(el.getAttribute('datetime')).toBe(iso);
  });

  it('shows relative text (recent)', () => {
    const iso = new Date(Date.now() - 30_000).toISOString();
    render(<RelativeTime iso={iso} />);
    const el = screen.getByRole('time');
    // Should have some text content
    expect(el.textContent?.length).toBeGreaterThan(0);
  });
});
