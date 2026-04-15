import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CopyButton } from '@/components/domain/copy-button';

describe('CopyButton', () => {
  it('renders with default label', () => {
    render(<CopyButton text="some text" />);
    expect(screen.getByRole('button', { name: /Copiar/i })).toBeTruthy();
  });

  it('shows confirmation flash after click', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    render(<CopyButton text="some text" />);
    fireEvent.click(screen.getByRole('button', { name: /Copiar/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Copiado/i })).toBeTruthy();
    });
  });

  it('is keyboard accessible (button element)', () => {
    render(<CopyButton text="some text" />);
    const btn = screen.getByRole('button');
    expect(btn.tagName).toBe('BUTTON');
  });
});
