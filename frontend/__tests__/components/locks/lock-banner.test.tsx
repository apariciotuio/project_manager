/**
 * EP-17 G3 — LockBanner tests.
 * RED phase: fails until implementation.
 *
 * Banner shown when a section is locked by someone else.
 * Inline (not a modal) — no Dialog, no click-outside dismiss.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LockBanner } from '@/components/locks/lock-banner';

describe('LockBanner', () => {
  it('test_renders_holder_name', () => {
    render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
      />,
    );
    expect(screen.getByText(/Ana García/)).toBeTruthy();
  });

  it('test_shows_read_only_message', () => {
    render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
      />,
    );
    // Should communicate read-only state
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('test_shows_request_unlock_button_when_callback_provided', () => {
    render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
        onRequestUnlock={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /solicitar|request/i })).toBeTruthy();
  });

  it('test_no_request_button_when_no_callback', () => {
    render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
      />,
    );
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('test_request_unlock_button_calls_callback', async () => {
    const user = userEvent.setup();
    const onRequestUnlock = vi.fn();
    render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
        onRequestUnlock={onRequestUnlock}
      />,
    );
    await user.click(screen.getByRole('button', { name: /solicitar|request/i }));
    expect(onRequestUnlock).toHaveBeenCalledOnce();
  });

  it('test_renders_with_expires_at', () => {
    render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
        expiresAt="2026-04-18T10:05:00.000Z"
      />,
    );
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('test_accessible_role_status', () => {
    const { container } = render(
      <LockBanner
        holderDisplayName="Ana García"
        lockedSince="2026-04-18T10:00:00.000Z"
      />,
    );
    expect(container.querySelector('[role="status"]')).toBeTruthy();
  });
});
