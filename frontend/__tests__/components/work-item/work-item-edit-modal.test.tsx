import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

// next-intl mock — returns `${ns}.${key}` so tests assert against translation keys
vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

import { WorkItemEditModal } from '@/components/work-item/work-item-edit-modal';
import type { WorkItemResponse } from '@/lib/types/work-item';

const BASE_WORK_ITEM: WorkItemResponse = {
  id: 'wi-1',
  title: 'Fix login bug',
  type: 'bug',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: null,
  description: 'Broken on mobile',
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 45,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
};

function renderModal(
  props: Partial<{
    open: boolean;
    workItem: WorkItemResponse;
    onClose: () => void;
    onSaved: (updated: WorkItemResponse) => void;
  }> = {}
) {
  const onClose = props.onClose ?? vi.fn();
  const onSaved = props.onSaved ?? vi.fn();
  return render(
    <WorkItemEditModal
      open={props.open ?? true}
      workItem={props.workItem ?? BASE_WORK_ITEM}
      onClose={onClose}
      onSaved={onSaved}
    />
  );
}

// Translation-key regex helpers (mocked next-intl returns `${ns}.${key}`)
const RX_FIELD_TITLE = /modals\.workItemEdit\.fields\.title/i;
const RX_FIELD_DESC = /modals\.workItemEdit\.fields\.description/i;
const RX_PRIORITY_HIGH = /modals\.workItemEdit\.priority\.high/i;
const RX_TYPE_BUG = /^modals\.workItemEdit\.type\.bug$/i;
const RX_SAVE = /^common\.save$/i;
const RX_SAVING = /^common\.saving$/i;
const RX_CANCEL = /^common\.cancel$/i;

describe('WorkItemEditModal', () => {
  it('renders prefilled title input', () => {
    renderModal();
    const input = screen.getByLabelText(RX_FIELD_TITLE);
    expect(input).toHaveValue('Fix login bug');
  });

  it('renders prefilled description textarea', () => {
    renderModal();
    const textarea = screen.getByLabelText(RX_FIELD_DESC);
    expect(textarea).toHaveValue('Broken on mobile');
  });

  it('renders priority select prefilled with current value', () => {
    renderModal();
    const spans = screen.getAllByText(RX_PRIORITY_HIGH);
    expect(spans.length).toBeGreaterThan(0);
  });

  it('renders type select prefilled with current value', () => {
    renderModal();
    const spans = screen.getAllByText(RX_TYPE_BUG);
    expect(spans.length).toBeGreaterThan(0);
  });

  it('Save button is disabled when no field has changed', () => {
    renderModal();
    const saveBtn = screen.getByRole('button', { name: RX_SAVE });
    expect(saveBtn).toBeDisabled();
  });

  it('Save button is enabled when title changes', async () => {
    const user = userEvent.setup();
    renderModal();
    const input = screen.getByLabelText(RX_FIELD_TITLE);
    await user.clear(input);
    await user.type(input, 'New title');
    expect(screen.getByRole('button', { name: RX_SAVE })).not.toBeDisabled();
  });

  it('calls onClose when Cancel is clicked, no request fired', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    let patched = false;
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1', () => {
        patched = true;
        return HttpResponse.json({ data: BASE_WORK_ITEM });
      })
    );
    renderModal({ onClose });
    await user.click(screen.getByRole('button', { name: RX_CANCEL }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(patched).toBe(false);
  });

  it('PATCHes only changed fields and calls onSaved on 200', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    let patchBody: unknown;

    const UPDATED = { ...BASE_WORK_ITEM, title: 'Updated title' };
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1', async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ data: UPDATED });
      })
    );

    renderModal({ onSaved });

    const input = screen.getByLabelText(RX_FIELD_TITLE);
    await user.clear(input);
    await user.type(input, 'Updated title');

    await user.click(screen.getByRole('button', { name: RX_SAVE }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith(UPDATED);
    });
    // Only the changed field should be sent
    expect(patchBody).toEqual({ title: 'Updated title' });
  });

  it('shows spinner/pending state during submit', async () => {
    const user = userEvent.setup();
    let resolve: () => void;
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1', () =>
        new Promise((r) => {
          resolve = () => r(HttpResponse.json({ data: BASE_WORK_ITEM }));
        })
      )
    );

    renderModal();

    const input = screen.getByLabelText(RX_FIELD_TITLE);
    await user.clear(input);
    await user.type(input, 'Changed');
    await user.click(screen.getByRole('button', { name: RX_SAVE }));

    // During pending, button should be disabled / show loading text
    await waitFor(() => {
      expect(screen.getByRole('button', { name: RX_SAVING })).toBeDisabled();
    });

    resolve!();
  });

  it('shows field error below title when backend returns 400 with field=title', async () => {
    const user = userEvent.setup();
    server.use(
      http.patch('http://localhost/api/v1/work-items/wi-1', () =>
        HttpResponse.json(
          { error: { code: 'INVALID_TITLE', message: 'El título es obligatorio', field: 'title' } },
          { status: 400 }
        )
      )
    );

    renderModal();

    const input = screen.getByLabelText(RX_FIELD_TITLE);
    await user.clear(input);
    await user.type(input, 'x');

    await user.click(screen.getByRole('button', { name: RX_SAVE }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/El título es obligatorio/i);
    });
    // Modal stays open — title input still visible
    expect(screen.getByLabelText(RX_FIELD_TITLE)).toBeInTheDocument();
  });

  it('does not render when open=false', () => {
    renderModal({ open: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('does not send request and closes on Cancel even after typing', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal({ onClose });
    await user.type(screen.getByLabelText(RX_FIELD_TITLE), ' extra');
    await user.click(screen.getByRole('button', { name: RX_CANCEL }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
