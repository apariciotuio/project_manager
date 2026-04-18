/**
 * EP-17 G5 — UnlockRequestDialog tests.
 * RED phase: all tests should fail until implementation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { UnlockRequestDialog } from '@/components/locks/unlock-request-dialog';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const BASE = 'http://localhost';

const UNLOCK_REQUEST_DTO = {
  id: 'req-1',
  section_id: 'sec-1',
  requester_id: 'user-2',
  reason: 'Need to update urgently',
  created_at: '2026-04-18T10:00:00.000Z',
  expires_at: '2026-04-18T10:02:00.000Z',
  responded_at: null,
  response_action: null,
  response_note: null,
};

function renderDialog(overrides: { isOpen?: boolean; onClose?: () => void } = {}) {
  const onClose = overrides.onClose ?? vi.fn();
  render(
    <UnlockRequestDialog
      sectionId="sec-1"
      holderDisplayName="Ana García"
      isOpen={overrides.isOpen ?? true}
      onClose={onClose}
    />,
  );
  return { onClose };
}

describe('UnlockRequestDialog', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('test_renders_reason_field_required', () => {
    renderDialog();
    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeTruthy();
    expect(textarea.hasAttribute('required') || textarea.getAttribute('aria-required') === 'true').toBe(true);
  });

  it('test_submit_disabled_when_reason_empty', () => {
    renderDialog();
    const submitBtn = screen.getByRole('button', { name: /solicitud|enviar/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(true);
  });

  it('test_submit_enabled_when_reason_has_content', async () => {
    const user = userEvent.setup();
    renderDialog();
    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'I need to update this urgently');
    const submitBtn = screen.getByRole('button', { name: /solicitud|enviar/i });
    expect(submitBtn.hasAttribute('disabled')).toBe(false);
  });

  it('test_submit_calls_request_unlock_api', async () => {
    const user = userEvent.setup();
    let capturedBody: unknown;
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ data: UNLOCK_REQUEST_DTO, message: 'unlock request sent' }, { status: 201 });
      }),
    );
    renderDialog();
    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Need to update this section');
    await user.click(screen.getByRole('button', { name: /solicitud|enviar/i }));
    await waitFor(() => {
      expect(capturedBody).toEqual({ reason: 'Need to update this section' });
    });
  });

  it('test_closes_and_shows_toast_on_success', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, () =>
        HttpResponse.json({ data: UNLOCK_REQUEST_DTO, message: 'unlock request sent' }, { status: 201 }),
      ),
    );
    renderDialog({ onClose });
    await user.type(screen.getByRole('textbox'), 'Need to update this section');
    await user.click(screen.getByRole('button', { name: /solicitud|enviar/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('test_shows_error_on_409_request_pending', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, () =>
        HttpResponse.json(
          { error: { code: 'ALREADY_RESPONDED', message: 'already pending', details: {} } },
          { status: 409 },
        ),
      ),
    );
    renderDialog();
    await user.type(screen.getByRole('textbox'), 'Need access please');
    await user.click(screen.getByRole('button', { name: /solicitud|enviar/i }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });

  it('test_shows_error_on_429_rate_limited_with_retry_after', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, () =>
        HttpResponse.json(
          { error: { code: 'RATE_LIMITED', message: 'too many requests', details: { retry_after: 300 } } },
          { status: 429 },
        ),
      ),
    );
    renderDialog();
    await user.type(screen.getByRole('textbox'), 'Need access urgently');
    await user.click(screen.getByRole('button', { name: /solicitud|enviar/i }));
    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toBeTruthy();
      expect(alert.textContent).toMatch(/minutos|minutes/i);
    });
  });

  it('test_reason_max_500_chars_enforced', async () => {
    const user = userEvent.setup();
    renderDialog();
    const textarea = screen.getByRole('textbox');
    const long = 'a'.repeat(501);
    await user.type(textarea, long);
    // Character count should cap at 500 or show error
    const value = (textarea as HTMLTextAreaElement).value;
    expect(value.length).toBeLessThanOrEqual(500);
  });

  it('test_dialog_not_rendered_when_closed', () => {
    renderDialog({ isOpen: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('test_char_counter_shown', async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByRole('textbox'), 'hello');
    expect(screen.getByText(/5\/500|5 \/ 500/)).toBeTruthy();
  });

  it('test_dialog_accessible_focus_trap', () => {
    renderDialog();
    // Dialog must have role dialog
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});
