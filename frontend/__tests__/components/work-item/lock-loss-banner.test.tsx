/**
 * EP-17 G6 — LockLossBanner tests.
 * Banner shown when user's lock was force-released or expired.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LockLossBanner } from '@/components/work-item/lock-loss-banner';

describe('LockLossBanner', () => {
  it('renders banner with lock-loss copy', () => {
    render(<LockLossBanner onReacquire={vi.fn()} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('status').textContent).toMatch(/lock|bloqueo/i);
  });

  it('displays reacquire button', () => {
    render(<LockLossBanner onReacquire={vi.fn()} />);
    expect(
      screen.getByRole('button', { name: /reacquire|volver a bloquear/i }),
    ).toBeInTheDocument();
  });

  it('calls onReacquire when button is clicked', async () => {
    const onReacquire = vi.fn();
    render(<LockLossBanner onReacquire={onReacquire} />);
    await userEvent.click(screen.getByRole('button', { name: /reacquire|volver a bloquear/i }));
    expect(onReacquire).toHaveBeenCalledOnce();
  });

  it('mentions unsaved changes are safe', () => {
    render(<LockLossBanner onReacquire={vi.fn()} />);
    expect(screen.getByRole('status').textContent).toMatch(/unsaved|sin guardar/i);
  });

  it('does not auto-dismiss (banner persists after render)', () => {
    const { unmount } = render(<LockLossBanner onReacquire={vi.fn()} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    unmount();
  });

  it('disables reacquire button while acquiring', () => {
    render(<LockLossBanner onReacquire={vi.fn()} isAcquiring />);
    expect(screen.getByRole('button', { name: /reacquire|volver a bloquear/i })).toBeDisabled();
  });

  it('renders without crashing when no props besides onReacquire', () => {
    const { container } = render(<LockLossBanner onReacquire={vi.fn()} />);
    expect(container.firstChild).not.toBeNull();
  });
});
