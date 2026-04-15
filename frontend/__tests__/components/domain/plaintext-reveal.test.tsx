import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PlaintextReveal } from '@/components/domain/plaintext-reveal';

describe('PlaintextReveal', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders hidden by default', () => {
    render(<PlaintextReveal value="secret-token-123" />);
    expect(screen.queryByText('secret-token-123')).toBeNull();
    expect(screen.getByRole('button', { name: /Mostrar/i })).toBeTruthy();
  });

  it('reveals content after clicking show button', () => {
    render(<PlaintextReveal value="secret-token-123" />);
    fireEvent.click(screen.getByRole('button', { name: /Mostrar/i }));
    expect(screen.getByText('secret-token-123')).toBeTruthy();
  });

  it('auto-clears after autoClearMs', async () => {
    render(<PlaintextReveal value="secret-token-123" autoClearMs={5000} />);
    fireEvent.click(screen.getByRole('button', { name: /Mostrar/i }));
    expect(screen.getByText('secret-token-123')).toBeTruthy();

    await act(async () => {
      vi.advanceTimersByTime(5001);
    });

    expect(screen.queryByText('secret-token-123')).toBeNull();
  });

  it('does NOT write to localStorage', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    render(<PlaintextReveal value="secret-token-123" />);
    fireEvent.click(screen.getByRole('button', { name: /Mostrar/i }));
    expect(setItem).not.toHaveBeenCalled();
  });

  it('does NOT write to sessionStorage', () => {
    const setItem = vi.spyOn(window.sessionStorage, 'setItem');
    render(<PlaintextReveal value="secret-token-123" />);
    fireEvent.click(screen.getByRole('button', { name: /Mostrar/i }));
    expect(setItem).not.toHaveBeenCalled();
  });

  it('hides on close button click', () => {
    render(<PlaintextReveal value="secret-token-123" />);
    fireEvent.click(screen.getByRole('button', { name: /Mostrar/i }));
    expect(screen.getByText('secret-token-123')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Ocultar/i }));
    expect(screen.queryByText('secret-token-123')).toBeNull();
  });
});
