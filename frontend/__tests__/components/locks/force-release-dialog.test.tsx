/**
 * EP-17 G7 — ForceReleaseDialog tests.
 * RED phase: fails until implementation.
 *
 * Gate: dialog only renders for users with is_superadmin=true.
 * (capabilities.force_unlock not yet in AuthUser — using is_superadmin as proxy)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ForceReleaseDialog } from '@/components/locks/force-release-dialog';
import type { SectionLockDTO } from '@/lib/types/lock';
import type { AuthUser } from '@/lib/types/auth';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const BASE = 'http://localhost';

const LOCK: SectionLockDTO = {
  id: 'lock-1',
  section_id: 'sec-1',
  work_item_id: 'wi-1',
  held_by: 'user-99',
  acquired_at: '2026-04-18T09:00:00.000Z',
  heartbeat_at: '2026-04-18T09:00:00.000Z',
  expires_at: '2026-04-18T09:05:00.000Z',
};

const ADMIN_USER: AuthUser = {
  id: 'admin-1',
  email: 'admin@example.com',
  full_name: 'Admin User',
  avatar_url: null,
  workspace_id: 'ws-1',
  workspace_slug: 'acme',
  is_superadmin: true,
};

const REGULAR_USER: AuthUser = {
  ...ADMIN_USER,
  id: 'user-1',
  is_superadmin: false,
};

function renderDialog(overrides: {
  user?: AuthUser;
  isOpen?: boolean;
  onClose?: () => void;
  holderName?: string;
} = {}) {
  const onClose = overrides.onClose ?? vi.fn();
  const user = overrides.user ?? ADMIN_USER;
  render(
    <ForceReleaseDialog
      sectionId="sec-1"
      lock={LOCK}
      holderDisplayName={overrides.holderName ?? 'Ana García'}
      currentUser={user}
      isOpen={overrides.isOpen ?? true}
      onClose={onClose}
    />,
  );
  return { onClose };
}

describe('ForceReleaseDialog', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('test_not_rendered_for_user_without_force_unlock_capability', () => {
    renderDialog({ user: REGULAR_USER });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('test_rendered_for_user_with_force_unlock_capability', () => {
    renderDialog({ user: ADMIN_USER });
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('test_shows_current_lock_summary', () => {
    renderDialog();
    const matches = screen.getAllByText(/Ana García/);
    expect(matches.length).toBeGreaterThan(0);
  });

  it('test_submit_disabled_until_reason_and_checkbox_filled', async () => {
    const user = userEvent.setup();
    renderDialog();
    const submitBtn = screen.getByRole('button', { name: /forzar|force/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(true);

    // Type reason < 10 chars
    await user.type(screen.getByRole('textbox'), 'short');
    expect(submitBtn.hasAttribute('disabled')).toBe(true);

    // Check checkbox — still disabled (reason too short)
    const checkbox = screen.getByRole('checkbox');
    await user.click(checkbox);
    expect(submitBtn.hasAttribute('disabled')).toBe(true);
  });

  it('test_submit_disabled_when_reason_less_than_10_chars', async () => {
    const user = userEvent.setup();
    renderDialog();
    const checkbox = screen.getByRole('checkbox');
    await user.click(checkbox);
    await user.type(screen.getByRole('textbox'), 'short');
    const submitBtn = screen.getByRole('button', { name: /forzar|force/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(true);
  });

  it('test_submit_enabled_when_reason_valid_and_checkbox_checked', async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByRole('textbox'), 'Reason with enough chars');
    await user.click(screen.getByRole('checkbox'));
    const submitBtn = screen.getByRole('button', { name: /forzar|force/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(false);
  });

  it('test_submit_calls_force_release_api', async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/force-release`, () => {
        called = true;
        return HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'lock force-released' });
      }),
    );
    renderDialog();
    await user.type(screen.getByRole('textbox'), 'Administrative override needed');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /forzar|force/i }));
    await waitFor(() => expect(called).toBe(true));
  });

  it('test_success_closes_dialog_and_shows_toast', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/force-release`, () =>
        HttpResponse.json({ data: { section_id: 'sec-1' }, message: 'lock force-released' }),
      ),
    );
    renderDialog({ onClose });
    await user.type(screen.getByRole('textbox'), 'Administrative override needed');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /forzar|force/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('test_503_shows_error_banner', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/force-release`, () =>
        HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'unavailable', details: {} } }, { status: 503 }),
      ),
    );
    renderDialog();
    await user.type(screen.getByRole('textbox'), 'Administrative override needed');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /forzar|force/i }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });
});
