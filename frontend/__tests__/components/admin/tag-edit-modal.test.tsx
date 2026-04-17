import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { TagEditModal } from '@/components/admin/tag-edit-modal';
import type { Tag } from '@/lib/types/api';

const BASE_TAG: Tag = {
  id: 'tag-1',
  name: 'urgent',
  color: '#ff0000',
  archived: false,
  created_at: '2026-01-01T00:00:00Z',
};

function renderModal(
  props: Partial<{
    open: boolean;
    tag: Tag;
    onClose: () => void;
    onSaved: (updated: Tag) => void;
  }> = {}
) {
  const onClose = props.onClose ?? vi.fn();
  const onSaved = props.onSaved ?? vi.fn();
  return render(
    <TagEditModal
      open={props.open ?? true}
      tag={props.tag ?? BASE_TAG}
      onClose={onClose}
      onSaved={onSaved}
    />
  );
}

describe('TagEditModal', () => {
  it('renders prefilled name input', () => {
    renderModal();
    expect(screen.getByRole('textbox', { name: /nombre/i })).toHaveValue('urgent');
  });

  it('Save button is disabled when no field has changed', () => {
    renderModal();
    expect(screen.getByRole('button', { name: /guardar/i })).toBeDisabled();
  });

  it('Save button is enabled when name changes', async () => {
    const user = userEvent.setup();
    renderModal();
    const input = screen.getByRole('textbox', { name: /nombre/i });
    await user.clear(input);
    await user.type(input, 'critical');
    expect(screen.getByRole('button', { name: /guardar/i })).not.toBeDisabled();
  });

  it('calls onClose when Cancel clicked, no request fired', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    let patched = false;
    server.use(
      http.patch('http://localhost/api/v1/tags/tag-1', () => {
        patched = true;
        return HttpResponse.json({ data: BASE_TAG });
      })
    );
    renderModal({ onClose });
    await user.click(screen.getByRole('button', { name: /cancelar/i }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(patched).toBe(false);
  });

  it('PATCHes only changed name and calls onSaved on 200', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    let patchBody: unknown;

    const UPDATED = { ...BASE_TAG, name: 'blocker' };
    server.use(
      http.patch('http://localhost/api/v1/tags/tag-1', async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ data: UPDATED });
      })
    );

    renderModal({ onSaved });
    const input = screen.getByRole('textbox', { name: /nombre/i });
    await user.clear(input);
    await user.type(input, 'blocker');
    await user.click(screen.getByRole('button', { name: /guardar/i }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith(UPDATED);
    });
    // Only changed field sent
    expect(patchBody).toEqual({ name: 'blocker' });
  });

  it('shows field error below name when backend returns 409 TAG_NAME_TAKEN', async () => {
    const user = userEvent.setup();
    server.use(
      http.patch('http://localhost/api/v1/tags/tag-1', () =>
        HttpResponse.json(
          { error: { code: 'TAG_NAME_TAKEN', message: "tag 'blocker' already exists", field: 'name' } },
          { status: 409 }
        )
      )
    );

    renderModal();
    const input = screen.getByRole('textbox', { name: /nombre/i });
    await user.clear(input);
    await user.type(input, 'blocker');
    await user.click(screen.getByRole('button', { name: /guardar/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/already exists/i);
    });
    // Modal stays open
    expect(screen.getByRole('textbox', { name: /nombre/i })).toBeInTheDocument();
  });

  it('enables Save when color changes', async () => {
    // Color picker changes fire via onChange; simulate directly
    const user = userEvent.setup();
    renderModal();
    // Type a custom color in the hex input that ColorPicker exposes
    const hexInput = screen.getByPlaceholderText('#rrggbb');
    await user.clear(hexInput);
    await user.type(hexInput, '#00ff00');
    // Wait for debounce (150ms) or just check that save enables after input
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /guardar/i })).not.toBeDisabled();
    }, { timeout: 500 });
  });

  it('PATCHes color when only color changes', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    let patchBody: unknown;

    const UPDATED = { ...BASE_TAG, color: '#00ff00' };
    server.use(
      http.patch('http://localhost/api/v1/tags/tag-1', async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ data: UPDATED });
      })
    );

    renderModal({ onSaved });
    const hexInput = screen.getByPlaceholderText('#rrggbb');
    await user.clear(hexInput);
    await user.type(hexInput, '#00ff00');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /guardar/i })).not.toBeDisabled();
    }, { timeout: 500 });

    await user.click(screen.getByRole('button', { name: /guardar/i }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith(UPDATED);
    });
    // color must be in the patch body
    expect(patchBody).toMatchObject({ color: '#00ff00' });
    expect((patchBody as Record<string, unknown>)['name']).toBeUndefined();
  });

  it('does not render when open=false', () => {
    renderModal({ open: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows archived indicator when tag is archived', () => {
    renderModal({ tag: { ...BASE_TAG, archived: true } });
    expect(screen.getByText(/archivada/i)).toBeInTheDocument();
  });
});
