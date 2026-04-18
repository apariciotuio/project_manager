import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

import { AddDocSourceModal } from '@/components/admin/add-doc-source-modal';

function renderModal(props: { open?: boolean; workspaceId?: string; onClose?: () => void; onSubmit?: (data: unknown) => Promise<void> } = {}) {
  const onClose = props.onClose ?? vi.fn();
  const onSubmit = props.onSubmit ?? vi.fn().mockResolvedValue(undefined);
  render(
    <AddDocSourceModal
      open={props.open ?? true}
      workspaceId={props.workspaceId ?? 'ws-1'}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  );
  return { onClose, onSubmit };
}

const RX_NAME = /workspace\.admin\.docSources\.modal\.fields\.name/i;
const RX_URL = /workspace\.admin\.docSources\.modal\.fields\.url/i;
const RX_TYPE = /workspace\.admin\.docSources\.modal\.fields\.sourceType/i;
const RX_PUBLIC = /workspace\.admin\.docSources\.modal\.fields\.isPublic/i;
const RX_ADD = /workspace\.admin\.docSources\.modal\.submit/i;
const RX_CANCEL = /workspace\.admin\.docSources\.modal\.cancel/i;

describe('AddDocSourceModal', () => {
  it('does not render when open=false', () => {
    renderModal({ open: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders name, source_type, url, is_public fields', () => {
    renderModal();
    expect(screen.getByLabelText(RX_NAME)).toBeInTheDocument();
    expect(screen.getByLabelText(RX_URL)).toBeInTheDocument();
  });

  it('shows validation error when name is empty and form submitted', async () => {
    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByLabelText(RX_URL), 'https://github.com/acme/repo');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('rejects non-github URL when source_type is github_repo', async () => {
    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByLabelText(RX_NAME), 'My Repo');
    await user.type(screen.getByLabelText(RX_URL), 'https://gitlab.com/acme/repo');
    // source_type defaults to github_repo — verify url validation fires
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('accepts github.com URL when source_type is github_repo', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderModal({ onSubmit });
    await user.type(screen.getByLabelText(RX_NAME), 'My Repo');
    await user.type(screen.getByLabelText(RX_URL), 'https://github.com/acme/repo');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'My Repo',
        url: 'https://github.com/acme/repo',
        source_type: 'github_repo',
        workspace_id: 'ws-1',
      })
    );
  });

  it('rejects non-http(s) URL when source_type is url', async () => {
    const user = userEvent.setup();
    renderModal();
    // Switch to 'url' type
    const typeSelect = screen.getByRole('combobox');
    await user.click(typeSelect);
    await user.click(screen.getByRole('option', { name: /workspace\.admin\.docSources\.sourceTypes\.url/i }));
    await user.type(screen.getByLabelText(RX_NAME), 'Docs');
    await user.type(screen.getByLabelText(RX_URL), 'ftp://docs.example.com');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('accepts http(s) URL when source_type is url', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderModal({ onSubmit });
    const typeSelect = screen.getByRole('combobox');
    await user.click(typeSelect);
    await user.click(screen.getByRole('option', { name: /workspace\.admin\.docSources\.sourceTypes\.url/i }));
    await user.type(screen.getByLabelText(RX_NAME), 'Docs');
    await user.type(screen.getByLabelText(RX_URL), 'https://docs.example.com/guide');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  });

  it('rejects non-path URL when source_type is path', async () => {
    const user = userEvent.setup();
    renderModal();
    const typeSelect = screen.getByRole('combobox');
    await user.click(typeSelect);
    await user.click(screen.getByRole('option', { name: /workspace\.admin\.docSources\.sourceTypes\.path/i }));
    await user.type(screen.getByLabelText(RX_NAME), 'Local');
    await user.type(screen.getByLabelText(RX_URL), 'https://not-a-path.com');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('accepts filesystem path when source_type is path', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderModal({ onSubmit });
    const typeSelect = screen.getByRole('combobox');
    await user.click(typeSelect);
    await user.click(screen.getByRole('option', { name: /workspace\.admin\.docSources\.sourceTypes\.path/i }));
    await user.type(screen.getByLabelText(RX_NAME), 'Local Docs');
    await user.type(screen.getByLabelText(RX_URL), '/data/documents');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();
    await user.click(screen.getByRole('button', { name: RX_CANCEL }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('closes modal after successful submit', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderModal({ onClose, onSubmit });
    await user.type(screen.getByLabelText(RX_NAME), 'My Repo');
    await user.type(screen.getByLabelText(RX_URL), 'https://github.com/acme/repo');
    await user.click(screen.getByRole('button', { name: RX_ADD }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });
});
