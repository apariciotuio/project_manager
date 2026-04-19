/**
 * EP-17 G3 — UnlockRequestDialog (work-item path alias) tests.
 * Imports from the work-item barrel to verify the export is wired correctly,
 * and validates the full interaction contract.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { UnlockRequestDialog } from '@/components/work-item/unlock-request-dialog';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const BASE = 'http://localhost';

function renderDialog(overrides: { isOpen?: boolean; onClose?: () => void } = {}) {
  const onClose = overrides.onClose ?? vi.fn();
  render(
    <UnlockRequestDialog
      sectionId="sec-1"
      holderDisplayName="Alice"
      isOpen={overrides.isOpen ?? true}
      onClose={onClose}
    />,
  );
  return { onClose };
}

describe('UnlockRequestDialog (work-item export)', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders dialog with reason textarea when open', () => {
    renderDialog();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('submit button disabled when reason is empty', () => {
    renderDialog();
    const btn = screen.getByRole('button', { name: /enviar|send/i });
    expect(btn).toBeDisabled();
  });

  it('character counter updates as user types', async () => {
    renderDialog();
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'hello');
    expect(screen.getByText(/5\s*\/\s*500/)).toBeInTheDocument();
  });

  it('submit button enabled when reason is non-empty', async () => {
    renderDialog();
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'Please release');
    const btn = screen.getByRole('button', { name: /enviar|send/i });
    expect(btn).not.toBeDisabled();
  });

  it('calls onClose after successful submission', async () => {
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, () =>
        HttpResponse.json({ data: { id: 'req-1' }, message: 'ok' }),
      ),
    );
    const { onClose } = renderDialog();
    await userEvent.type(screen.getByRole('textbox'), 'Please release');
    await userEvent.click(screen.getByRole('button', { name: /enviar|send/i }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('shows inline error on 409 conflict', async () => {
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, () =>
        HttpResponse.json({ error: { code: 'LOCK_CONFLICT', message: 'Conflict' } }, { status: 409 }),
      ),
    );
    renderDialog();
    await userEvent.type(screen.getByRole('textbox'), 'Please release');
    await userEvent.click(screen.getByRole('button', { name: /enviar|send/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });

  it('does not close on 409 error', async () => {
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/unlock-request`, () =>
        HttpResponse.json({ error: { code: 'LOCK_CONFLICT', message: 'Conflict' } }, { status: 409 }),
      ),
    );
    const { onClose } = renderDialog();
    await userEvent.type(screen.getByRole('textbox'), 'Please release');
    await userEvent.click(screen.getByRole('button', { name: /enviar|send/i }));
    await waitFor(() => screen.getByRole('alert'));
    expect(onClose).not.toHaveBeenCalled();
  });
});
