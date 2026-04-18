/**
 * EP-17 G6 — HolderResponsePanel tests.
 * RED phase: fails until implementation.
 *
 * Panel shown to the lock holder when an unlock request arrives via SSE.
 * NOT dismissible by Escape or click-outside.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { HolderResponsePanel } from '@/components/locks/holder-response-panel';
import type { UnlockRequestDTO } from '@/lib/types/lock';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const BASE = 'http://localhost';

const UNLOCK_REQUEST: UnlockRequestDTO = {
  id: 'req-1',
  section_id: 'sec-1',
  requester_id: 'user-2',
  reason: 'Need to fix a critical issue',
  created_at: '2026-04-18T10:00:00.000Z',
  // expires 120 seconds from now
  expires_at: new Date(Date.now() + 120_000).toISOString(),
  responded_at: null,
  response_action: null,
  response_note: null,
};

function renderPanel(overrides: {
  request?: UnlockRequestDTO;
  requesterName?: string;
  onRespond?: (decision: 'release' | 'ignore') => void;
} = {}) {
  const onRespond = overrides.onRespond ?? vi.fn();
  render(
    <HolderResponsePanel
      sectionId="sec-1"
      request={overrides.request ?? UNLOCK_REQUEST}
      requesterDisplayName={overrides.requesterName ?? 'Carlos López'}
      onRespond={onRespond}
    />,
  );
  return { onRespond };
}

describe('HolderResponsePanel', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    server.resetHandlers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('test_renders_requester_info_and_reason', () => {
    renderPanel();
    expect(screen.getByText(/Carlos López/)).toBeTruthy();
    expect(screen.getByText(/Need to fix a critical issue/)).toBeTruthy();
  });

  it('test_shows_countdown_initially', () => {
    renderPanel();
    // Should show mm:ss countdown
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeTruthy();
  });

  it('test_release_button_present', () => {
    renderPanel();
    expect(screen.getByRole('button', { name: /liberar|release/i })).toBeTruthy();
  });

  it('test_ignore_button_present', () => {
    renderPanel();
    expect(screen.getByRole('button', { name: /ignorar|ignore/i })).toBeTruthy();
  });

  it('test_release_button_calls_respond_api_with_release', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let capturedBody: unknown;
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/respond`, async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({
          data: { ...UNLOCK_REQUEST, responded_at: new Date().toISOString(), response_action: 'accept' },
          message: 'request accepted',
        });
      }),
    );
    const onRespond = vi.fn();
    renderPanel({ onRespond });
    await user.click(screen.getByRole('button', { name: /liberar|release/i }));
    await waitFor(() => {
      expect((capturedBody as Record<string, unknown>)['action']).toBe('accept');
    });
    expect(onRespond).toHaveBeenCalledWith('release');
  });

  it('test_ignore_button_calls_respond_api_with_ignore', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let capturedBody: unknown;
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/respond`, async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({
          data: { ...UNLOCK_REQUEST, responded_at: new Date().toISOString(), response_action: 'decline' },
          message: 'request declined',
        });
      }),
    );
    const onRespond = vi.fn();
    renderPanel({ onRespond });
    await user.click(screen.getByRole('button', { name: /ignorar|ignore/i }));
    await waitFor(() => {
      expect((capturedBody as Record<string, unknown>)['action']).toBe('decline');
    });
    expect(onRespond).toHaveBeenCalledWith('ignore');
  });

  it('test_panel_not_dismissible_by_escape', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderPanel();
    const panel = screen.getByRole('alertdialog');
    expect(panel).toBeTruthy();
    await user.keyboard('{Escape}');
    // Panel should still be present
    expect(screen.getByRole('alertdialog')).toBeTruthy();
  });

  it('test_panel_has_accessible_role', () => {
    renderPanel();
    expect(screen.getByRole('alertdialog')).toBeTruthy();
  });

  it('test_panel_removed_after_respond', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/respond`, () =>
        HttpResponse.json({
          data: { ...UNLOCK_REQUEST, responded_at: new Date().toISOString(), response_action: 'accept' },
          message: 'ok',
        }),
      ),
    );
    const onRespond = vi.fn();
    renderPanel({ onRespond });
    await user.click(screen.getByRole('button', { name: /liberar|release/i }));
    await waitFor(() => expect(onRespond).toHaveBeenCalled());
  });

  it('test_countdown_interval_cleared_when_expired', async () => {
    // Request expires 100ms from now
    const expiresAt = new Date(Date.now() + 100).toISOString();
    renderPanel({ request: { ...UNLOCK_REQUEST, expires_at: expiresAt } });
    
    // Show countdown is running
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeTruthy();
    
    // Advance timers past expiry (200ms total)
    vi.advanceTimersByTime(200);
    
    // Verify interval has stopped by advancing again — should not cause additional renders
    const countdownBefore = screen.getByText(/00:00|00:01/).textContent;
    vi.advanceTimersByTime(1000);
    const countdownAfter = screen.getByText(/00:00|00:01/).textContent;
    
    // Countdown should be the same or not have decremented further
    expect(countdownBefore).toBe(countdownAfter);
    
    // Panel should still be rendered (it doesn't auto-dismiss)
    expect(screen.getByRole('alertdialog')).toBeTruthy();
  });
});
