import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ReassignOwnerModal } from '@/components/work-item/reassign-owner-modal';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

const MEMBERS = [
  { id: 'user-1', email: 'alice@co.com', full_name: 'Alice Doe', avatar_url: null, role: 'member' },
  { id: 'user-2', email: 'bob@co.com', full_name: 'Bob Smith', avatar_url: null, role: 'member' },
  { id: 'user-3', email: 'eve@co.com', full_name: 'Eve Ng', avatar_url: null, role: 'admin' },
];

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

function mockMembers() {
  server.use(
    http.get('http://localhost/api/v1/workspaces/members', () =>
      HttpResponse.json({ data: MEMBERS }),
    ),
  );
}

describe('ReassignOwnerModal', () => {
  it('does not render when open=false', () => {
    render(
      <ReassignOwnerModal open={false} workItem={WORK_ITEM} onClose={vi.fn()} onReassigned={vi.fn()} />,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders member select excluding the current owner', async () => {
    mockMembers();
    render(
      <ReassignOwnerModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onReassigned={vi.fn()} />,
    );
    const trigger = await screen.findByRole('combobox', {
      name: /workspace\.itemDetail\.reassign\.newOwnerLabel/i,
    });
    await userEvent.click(trigger);
    // Current owner (Alice, user-1) is not in the option list.
    expect(screen.queryByRole('option', { name: /Alice Doe/i })).toBeNull();
    expect(screen.getByRole('option', { name: /Bob Smith/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Eve Ng/i })).toBeInTheDocument();
  });

  it('confirm disabled until a new owner is selected', async () => {
    mockMembers();
    const user = userEvent.setup();
    render(
      <ReassignOwnerModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onReassigned={vi.fn()} />,
    );

    const confirm = screen.getByRole('button', {
      name: /workspace\.itemDetail\.reassign\.confirm/i,
    });
    expect(confirm).toBeDisabled();

    const trigger = await screen.findByRole('combobox', {
      name: /workspace\.itemDetail\.reassign\.newOwnerLabel/i,
    });
    await user.click(trigger);
    await user.click(await screen.findByRole('option', { name: /Bob Smith/i }));

    expect(confirm).not.toBeDisabled();
  });

  it('submits new_owner_id + reason and fires onReassigned on success', async () => {
    mockMembers();
    const user = userEvent.setup();
    const onReassigned = vi.fn();
    let bodyReceived: unknown;
    const reassigned = { ...WORK_ITEM, owner_id: 'user-2' };
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', async ({ request }) => {
        bodyReceived = await request.json();
        return HttpResponse.json({ data: reassigned });
      }),
    );

    render(
      <ReassignOwnerModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onReassigned={onReassigned} />,
    );

    const trigger = await screen.findByRole('combobox', {
      name: /workspace\.itemDetail\.reassign\.newOwnerLabel/i,
    });
    await user.click(trigger);
    await user.click(await screen.findByRole('option', { name: /Bob Smith/i }));

    await user.type(
      screen.getByRole('textbox', {
        name: /workspace\.itemDetail\.reassign\.reasonLabel/i,
      }),
      'On leave',
    );

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.reassign\.confirm/i }),
    );

    await waitFor(() => expect(onReassigned).toHaveBeenCalledWith(reassigned));
    expect(bodyReceived).toEqual({ new_owner_id: 'user-2', reason: 'On leave' });
  });

  it('shows alert on 403', async () => {
    mockMembers();
    const user = userEvent.setup();
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', () =>
        HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'not owner/admin' } }, { status: 403 }),
      ),
    );

    render(
      <ReassignOwnerModal open={true} workItem={WORK_ITEM} onClose={vi.fn()} onReassigned={vi.fn()} />,
    );

    const trigger = await screen.findByRole('combobox', {
      name: /workspace\.itemDetail\.reassign\.newOwnerLabel/i,
    });
    await user.click(trigger);
    await user.click(await screen.findByRole('option', { name: /Bob Smith/i }));

    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.reassign\.confirm/i }),
    );

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });
});
