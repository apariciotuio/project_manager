import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { StateTransitionPanel } from '@/components/work-item/state-transition-panel';
import type { WorkItemResponse } from '@/lib/types/work-item';

// next-intl returns keys so assertions don't depend on Spanish content.
vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

const WORK_ITEM: WorkItemResponse = {
  id: 'wi-1',
  title: 'Fix login bug',
  type: 'bug',
  state: 'draft',
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

describe('StateTransitionPanel', () => {
  it('renders the current state with an aria-labelled status', () => {
    const onTransition = vi.fn();
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={onTransition} />);
    expect(
      screen.getByRole('status', {
        name: /workspace\.itemDetail\.transitions\.heading.*workspace\.itemDetail\.transitions\.draft/i,
      }),
    ).toBeInTheDocument();
  });

  it('shows one button per available transition from current state', () => {
    const onTransition = vi.fn();
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={onTransition} />);
    // draft → in_clarification is the only valid edge from DRAFT.
    expect(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.in_clarification/i }),
    ).toBeInTheDocument();
  });

  it('shows a "no transitions" message when the work item is in a terminal state', () => {
    const terminal = { ...WORK_ITEM, state: 'exported' as const };
    const onTransition = vi.fn();
    render(<StateTransitionPanel workItem={terminal} onTransition={onTransition} />);
    expect(screen.getByText(/workspace\.itemDetail\.transitions\.noneAvailable/i)).toBeInTheDocument();
  });

  it('opens a confirm dialog when a transition button is clicked', async () => {
    const user = userEvent.setup();
    const onTransition = vi.fn();
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={onTransition} />);

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.in_clarification/i }),
    );
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  it('POSTs the transition and calls onTransition with the updated work item', async () => {
    const user = userEvent.setup();
    const onTransition = vi.fn();
    const transitioned = { ...WORK_ITEM, state: 'in_clarification' as const };
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json({ data: transitioned }),
      ),
    );
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={onTransition} />);

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.in_clarification/i }),
    );
    await waitFor(() => screen.getByRole('dialog'));

    // Fill reason and submit
    const reason = screen.getByRole('textbox', {
      name: /workspace\.itemDetail\.transitions\.reasonLabel/i,
    });
    await user.type(reason, 'Need more info');

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.confirm/i }),
    );

    await waitFor(() => expect(onTransition).toHaveBeenCalledWith(transitioned));
  });

  it('cancel button does not fire the request', async () => {
    const user = userEvent.setup();
    const onTransition = vi.fn();
    let called = false;
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', () => {
        called = true;
        return HttpResponse.json({ data: WORK_ITEM });
      }),
    );
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={onTransition} />);

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.in_clarification/i }),
    );
    await waitFor(() => screen.getByRole('dialog'));
    await user.click(
      screen.getByRole('button', { name: /common\.cancel/i }),
    );

    expect(called).toBe(false);
    expect(onTransition).not.toHaveBeenCalled();
  });

  it('shows an alert when the request fails', async () => {
    const user = userEvent.setup();
    const onTransition = vi.fn();
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/transitions', () =>
        HttpResponse.json(
          { error: { code: 'WORK_ITEM_INVALID_TRANSITION', message: 'invalid' } },
          { status: 422 },
        ),
      ),
    );
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={onTransition} />);

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.in_clarification/i }),
    );
    await waitFor(() => screen.getByRole('dialog'));
    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.transitions\.confirm/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(onTransition).not.toHaveBeenCalled();
  });
});

// ReadyGateBlockers integration with StateTransitionPanel
describe('StateTransitionPanel — ReadyGateBlockers integration', () => {
  const IN_CLARIFICATION_ITEM: WorkItemResponse = {
    ...WORK_ITEM,
    state: 'in_clarification',
  };

  it('shows ReadyGateBlockers inline when state has ready transition and gate is blocked', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ready-gate', () =>
        HttpResponse.json({
          data: {
            ok: false,
            blockers: [
              { code: 'VALIDATION_REQUIRED', rule_id: 'r1', label: 'Has AC', status: 'pending' },
            ],
          },
        }),
      ),
    );
    render(<StateTransitionPanel workItem={IN_CLARIFICATION_ITEM} onTransition={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByTestId('ready-gate-blockers')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('blocker-item-r1')).toBeInTheDocument();
  });

  it('does not render ReadyGateBlockers when gate is ok', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ready-gate', () =>
        HttpResponse.json({ data: { ok: true, blockers: [] } }),
      ),
    );
    const { container } = render(
      <StateTransitionPanel workItem={IN_CLARIFICATION_ITEM} onTransition={vi.fn()} />,
    );
    await waitFor(() =>
      expect(container.querySelector('[data-testid="ready-gate-blockers"]')).toBeNull(),
    );
  });

  it('does not render ReadyGateBlockers when current state has no ready transition', async () => {
    // draft → in_clarification only, no ready
    render(<StateTransitionPanel workItem={WORK_ITEM} onTransition={vi.fn()} />);
    expect(screen.queryByTestId('ready-gate-blockers')).not.toBeInTheDocument();
  });
});
