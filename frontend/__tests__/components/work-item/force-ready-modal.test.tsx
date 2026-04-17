import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ForceReadyModal } from '@/components/work-item/force-ready-modal';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

const WORK_ITEM: WorkItemResponse = {
  id: 'wi-1',
  title: 'Fix login bug',
  type: 'bug',
  state: 'in_clarification',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 40,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
};

describe('ForceReadyModal', () => {
  it('does not render when open=false', () => {
    render(
      <ForceReadyModal open={false} workItem={WORK_ITEM} onClose={vi.fn()} onForced={vi.fn()} />,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders title + justification textarea + confirm input when open', () => {
    render(
      <ForceReadyModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onForced={vi.fn()} />,
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.justificationLabel/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.typeToConfirmLabel/i }),
    ).toBeInTheDocument();
  });

  it('confirm is disabled until justification non-empty AND title typed exactly', async () => {
    const user = userEvent.setup();
    render(
      <ForceReadyModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onForced={vi.fn()} />,
    );
    const confirmBtn = screen.getByRole('button', {
      name: /workspace\.itemDetail\.forceReady\.confirm/i,
    });
    expect(confirmBtn).toBeDisabled();

    await user.type(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.justificationLabel/i }),
      'Ship for demo',
    );
    expect(confirmBtn).toBeDisabled();

    await user.type(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.typeToConfirmLabel/i }),
      'Fix login bug',
    );
    expect(confirmBtn).not.toBeDisabled();
  });

  it('calls the API and fires onForced with the updated work item on confirm', async () => {
    const user = userEvent.setup();
    const onForced = vi.fn();
    const overridden = {
      ...WORK_ITEM,
      state: 'ready' as const,
      has_override: true,
      override_justification: 'Ship for demo',
    };
    let bodyReceived: unknown;
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/force-ready', async ({ request }) => {
        bodyReceived = await request.json();
        return HttpResponse.json({ data: overridden });
      }),
    );

    render(
      <ForceReadyModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onForced={onForced} />,
    );

    await user.type(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.justificationLabel/i }),
      'Ship for demo',
    );
    await user.type(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.typeToConfirmLabel/i }),
      'Fix login bug',
    );
    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.forceReady\.confirm/i }),
    );

    await waitFor(() => expect(onForced).toHaveBeenCalledWith(overridden));
    expect(bodyReceived).toEqual({ justification: 'Ship for demo', confirmed: true });
  });

  it('shows an alert when the API returns 422', async () => {
    const user = userEvent.setup();
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/force-ready', () =>
        HttpResponse.json(
          { error: { code: 'VALIDATION_ERROR', message: 'justification too short' } },
          { status: 422 },
        ),
      ),
    );
    render(
      <ForceReadyModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onForced={vi.fn()} />,
    );
    await user.type(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.justificationLabel/i }),
      'x',
    );
    await user.type(
      screen.getByRole('textbox', { name: /workspace\.itemDetail\.forceReady\.typeToConfirmLabel/i }),
      'Fix login bug',
    );
    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.forceReady\.confirm/i }),
    );

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });

  it('cancel calls onClose and does not fire request', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    let hit = false;
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/force-ready', () => {
        hit = true;
        return HttpResponse.json({ data: WORK_ITEM });
      }),
    );
    render(
      <ForceReadyModal open={true} workItem={WORK_ITEM} onClose={onClose} onForced={vi.fn()} />,
    );
    await user.click(screen.getByRole('button', { name: /common\.cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(hit).toBe(false);
  });
});
