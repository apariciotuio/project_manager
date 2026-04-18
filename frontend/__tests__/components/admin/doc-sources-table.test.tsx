import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

import { DocSourcesTable } from '@/components/admin/doc-sources-table';
import type { DocSource } from '@/lib/types/puppet';

const SRC_INDEXED: DocSource = {
  id: 'src-1',
  name: 'Acme Docs',
  source_type: 'github_repo',
  url: 'https://github.com/acme/repo',
  is_public: true,
  status: 'indexed',
  last_indexed_at: '2026-04-17T12:00:00Z',
  item_count: 42,
};

const SRC_ERROR: DocSource = {
  id: 'src-2',
  name: 'Broken URL',
  source_type: 'url',
  url: 'https://broken.example.com',
  is_public: false,
  status: 'error',
  last_indexed_at: null,
  item_count: null,
  error_message: 'Connection refused',
};

const SRC_PENDING: DocSource = {
  id: 'src-3',
  name: 'New Source',
  source_type: 'path',
  url: '/data/docs',
  is_public: false,
  status: 'pending',
  last_indexed_at: null,
  item_count: null,
};

function renderTable(sources: DocSource[] = [SRC_INDEXED], onAddSource = vi.fn(), onDeleteSource = vi.fn()) {
  render(
    <DocSourcesTable
      sources={sources}
      isLoading={false}
      onAddSource={onAddSource}
      onDeleteSource={onDeleteSource}
    />
  );
  return { onAddSource, onDeleteSource };
}

describe('DocSourcesTable', () => {
  it('renders table with Name, Type, URL, Public, Status, Last Indexed, Actions columns', () => {
    renderTable();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.name/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.type/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.url/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.public/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.status/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.lastIndexed/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace\.admin\.docSources\.columns\.actions/i)).toBeInTheDocument();
  });

  it('renders source name and URL in table rows', () => {
    renderTable();
    expect(screen.getByText('Acme Docs')).toBeInTheDocument();
    expect(screen.getByText(/github\.com\/acme\/repo/i)).toBeInTheDocument();
  });

  it('renders status badge for each source', () => {
    renderTable();
    expect(screen.getByTestId('status-badge-src-1')).toBeInTheDocument();
  });

  it('error row shows error badge', () => {
    renderTable([SRC_ERROR]);
    const badge = screen.getByTestId('status-badge-src-2');
    expect(badge).toHaveAttribute('data-status', 'error');
  });

  it('error row has tooltip with error_message', () => {
    renderTable([SRC_ERROR]);
    const badge = screen.getByTestId('status-badge-src-2');
    expect(badge).toHaveAttribute('title', 'Connection refused');
  });

  it('"Add Source" button calls onAddSource', async () => {
    const user = userEvent.setup();
    const { onAddSource } = renderTable();
    await user.click(screen.getByRole('button', { name: /workspace\.admin\.docSources\.addButton/i }));
    expect(onAddSource).toHaveBeenCalledOnce();
  });

  it('delete button opens confirmation dialog', async () => {
    const user = userEvent.setup();
    renderTable();
    await user.click(screen.getByRole('button', { name: /workspace\.admin\.docSources\.deleteAria/i }));
    expect(
      screen.getByRole('dialog')
    ).toBeInTheDocument();
  });

  it('confirming delete calls onDeleteSource with source id', async () => {
    const user = userEvent.setup();
    const onDeleteSource = vi.fn().mockResolvedValue(undefined);
    renderTable([SRC_INDEXED], vi.fn(), onDeleteSource);
    await user.click(screen.getByRole('button', { name: /workspace\.admin\.docSources\.deleteAria/i }));
    await user.click(screen.getByRole('button', { name: /workspace\.admin\.docSources\.confirmDelete/i }));
    await waitFor(() => expect(onDeleteSource).toHaveBeenCalledWith('src-1'));
  });

  it('shows skeleton when isLoading', () => {
    render(
      <DocSourcesTable
        sources={[]}
        isLoading={true}
        onAddSource={vi.fn()}
        onDeleteSource={vi.fn()}
      />
    );
    expect(screen.getByTestId('doc-sources-skeleton')).toBeInTheDocument();
  });
});
