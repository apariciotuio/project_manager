import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { OwnerPanel } from '@/components/work-item/owner-panel';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

const MEMBERS = [
  { id: 'user-1', email: 'alice@co.com', full_name: 'Alice Doe', avatar_url: null, role: 'member' },
  { id: 'user-2', email: 'bob@co.com', full_name: 'Bob Smith', avatar_url: null, role: 'member' },
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

describe('OwnerPanel', () => {
  it('renders the current owner full_name resolved from the members list', async () => {
    mockMembers();
    render(<OwnerPanel workItem={WORK_ITEM} canReassign={false} onReassigned={vi.fn()} />);
    expect(await screen.findByText(/Alice Doe/)).toBeInTheDocument();
  });

  it('falls back to "unassigned" label when the owner is not in the members list', async () => {
    server.use(
      http.get('http://localhost/api/v1/workspaces/members', () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    render(<OwnerPanel workItem={WORK_ITEM} canReassign={false} onReassigned={vi.fn()} />);
    expect(
      await screen.findByText(/workspace\.itemDetail\.reassign\.unassigned/i),
    ).toBeInTheDocument();
  });

  it('shows the Reassign button when canReassign=true', async () => {
    mockMembers();
    render(<OwnerPanel workItem={WORK_ITEM} canReassign={true} onReassigned={vi.fn()} />);
    expect(
      await screen.findByRole('button', { name: /workspace\.itemDetail\.reassign\.button/i }),
    ).toBeInTheDocument();
  });

  it('hides the Reassign button when canReassign=false', async () => {
    mockMembers();
    render(<OwnerPanel workItem={WORK_ITEM} canReassign={false} onReassigned={vi.fn()} />);
    await screen.findByText(/Alice Doe/);
    expect(
      screen.queryByRole('button', { name: /workspace\.itemDetail\.reassign\.button/i }),
    ).toBeNull();
  });

  it('clicking Reassign opens the modal', async () => {
    mockMembers();
    const user = userEvent.setup();
    render(<OwnerPanel workItem={WORK_ITEM} canReassign={true} onReassigned={vi.fn()} />);

    await user.click(
      await screen.findByRole('button', { name: /workspace\.itemDetail\.reassign\.button/i }),
    );
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
  });

  it('propagates onReassigned after a successful reassign', async () => {
    mockMembers();
    const reassigned = { ...WORK_ITEM, owner_id: 'user-2' };
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1/owner', () =>
        HttpResponse.json({ data: reassigned }),
      ),
    );
    const onReassigned = vi.fn();
    const user = userEvent.setup();
    render(<OwnerPanel workItem={WORK_ITEM} canReassign={true} onReassigned={onReassigned} />);

    await user.click(
      await screen.findByRole('button', { name: /workspace\.itemDetail\.reassign\.button/i }),
    );
    const trigger = await screen.findByRole('combobox', {
      name: /workspace\.itemDetail\.reassign\.newOwnerLabel/i,
    });
    await user.click(trigger);
    await user.click(await screen.findByRole('option', { name: /Bob Smith/i }));
    await user.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.reassign\.confirm/i }),
    );

    await waitFor(() => expect(onReassigned).toHaveBeenCalledWith(reassigned));
  });
});
