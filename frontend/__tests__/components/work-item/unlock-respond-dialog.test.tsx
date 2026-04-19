/**
 * EP-17 G5 — UnlockRespondDialog (work-item path alias) tests.
 * Validates holder-response interaction from the work-item barrel export.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { UnlockRespondDialog } from '@/components/work-item/unlock-respond-dialog';
import type { UnlockRequestDTO } from '@/lib/types/lock';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const BASE = 'http://localhost';

const mockRequest: UnlockRequestDTO = {
  id: 'req-1',
  section_id: 'sec-1',
  requester_id: 'user-2',
  reason: 'Need to update urgently',
  created_at: '2026-04-18T10:00:00.000Z',
  expires_at: new Date(Date.now() + 120_000).toISOString(),
  responded_at: null,
  response_action: null,
  response_note: null,
};

function renderPanel(onRespond = vi.fn()) {
  render(
    <UnlockRespondDialog
      sectionId="sec-1"
      request={mockRequest}
      requesterDisplayName="Bob"
      onRespond={onRespond}
    />,
  );
  return { onRespond };
}

describe('UnlockRespondDialog (work-item export)', () => {
  beforeEach(() => {
    server.resetHandlers();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders panel with requester name', () => {
    renderPanel();
    expect(screen.getByText(/Bob/)).toBeInTheDocument();
  });

  it('shows countdown derived from expires_at', () => {
    renderPanel();
    expect(screen.getByText(/\d{2}:\d{2}/)).toBeInTheDocument();
  });

  it('has release and ignore buttons', () => {
    renderPanel();
    expect(screen.getByRole('button', { name: /liberar|release/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ignorar|ignore/i })).toBeInTheDocument();
  });

  it('calls onRespond("release") after accepting', async () => {
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/respond`, () =>
        HttpResponse.json({ data: { id: 'req-1', response_action: 'accept' }, message: 'ok' }),
      ),
    );
    const { onRespond } = renderPanel();
    await userEvent.click(screen.getByRole('button', { name: /liberar|release/i }));
    await waitFor(() => expect(onRespond).toHaveBeenCalledWith('release'));
  });

  it('calls onRespond("ignore") after declining', async () => {
    server.use(
      http.post(`${BASE}/api/v1/sections/sec-1/lock/respond`, () =>
        HttpResponse.json({ data: { id: 'req-1', response_action: 'decline' }, message: 'ok' }),
      ),
    );
    const { onRespond } = renderPanel();
    await userEvent.click(screen.getByRole('button', { name: /ignorar|ignore/i }));
    await waitFor(() => expect(onRespond).toHaveBeenCalledWith('ignore'));
  });

  it('has alertdialog role and is not dismissible by Escape', async () => {
    renderPanel();
    const panel = screen.getByRole('alertdialog');
    expect(panel).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });
});
