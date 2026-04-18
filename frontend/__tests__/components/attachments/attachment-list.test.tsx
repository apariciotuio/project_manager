import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { AttachmentList } from '@/components/attachments/attachment-list';
import type { AttachmentResponse } from '@/lib/types/attachment';

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'u1', full_name: 'Alice', is_superadmin: false },
  }),
}));

const ATTACHMENTS: AttachmentResponse[] = [
  {
    id: 'att1',
    filename: 'design.pdf',
    mime_type: 'application/pdf',
    size_bytes: 204800,
    size_human_readable: '200 KB',
    uploaded_by: 'u1',
    uploaded_by_name: 'Alice',
    created_at: '2026-04-01T10:00:00Z',
    download_url: '/api/v1/attachments/att1/download',
  },
  {
    id: 'att2',
    filename: 'screenshot.png',
    mime_type: 'image/png',
    size_bytes: 512000,
    size_human_readable: '500 KB',
    uploaded_by: 'u2',
    uploaded_by_name: 'Bob',
    created_at: '2026-04-02T11:00:00Z',
    download_url: '/api/v1/attachments/att2/download',
  },
];

describe('AttachmentList', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi1/attachments', () =>
        HttpResponse.json({ data: ATTACHMENTS }),
      ),
    );
  });

  it('renders loading skeleton initially', () => {
    render(<AttachmentList workItemId="wi1" canEdit={false} currentUserId="u1" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders attachment rows after load', async () => {
    render(<AttachmentList workItemId="wi1" canEdit={false} currentUserId="u1" />);
    await waitFor(() => expect(screen.getByText('design.pdf')).toBeInTheDocument());
    expect(screen.getByText('screenshot.png')).toBeInTheDocument();
    expect(screen.getByText(/200 KB/)).toBeInTheDocument();
    expect(screen.getByText(/500 KB/)).toBeInTheDocument();
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByText(/Bob/)).toBeInTheDocument();
  });

  it('shows empty state when no attachments', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi1/attachments', () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    render(<AttachmentList workItemId="wi1" canEdit={false} currentUserId="u1" />);
    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
  });

  it('shows delete button only for own attachments (owner of attachment)', async () => {
    render(<AttachmentList workItemId="wi1" canEdit={false} currentUserId="u1" />);
    await waitFor(() => expect(screen.getByText('design.pdf')).toBeInTheDocument());
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    // u1 owns att1 — only 1 delete button (not shown for att2 owned by u2)
    expect(deleteButtons).toHaveLength(1);
  });

  it('shows delete button for all attachments when superadmin', async () => {
    vi.mock('@/app/providers/auth-provider', () => ({
      useAuth: () => ({
        user: { id: 'admin', full_name: 'Admin', is_superadmin: true },
      }),
    }));
    server.use(
      http.get('http://localhost/api/v1/work-items/wi1/attachments', () =>
        HttpResponse.json({ data: ATTACHMENTS }),
      ),
    );
    // Re-render with superadmin - pass canEdit and currentUserId manually
    render(<AttachmentList workItemId="wi1" canEdit={true} currentUserId="admin" isSuperadmin />);
    await waitFor(() => expect(screen.getByText('design.pdf')).toBeInTheDocument());
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    expect(deleteButtons).toHaveLength(2);
  });

  it('delete triggers confirm dialog then API call and removes row', async () => {
    const user = userEvent.setup();
    server.use(
      http.delete('http://localhost/api/v1/attachments/att1', () =>
        HttpResponse.json({ data: null, message: 'Deleted' }, { status: 200 }),
      ),
    );
    render(<AttachmentList workItemId="wi1" canEdit={false} currentUserId="u1" />);
    await waitFor(() => expect(screen.getByText('design.pdf')).toBeInTheDocument());

    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    await user.click(deleteBtn);

    // Confirm dialog opens
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: /confirm|yes|delete/i });
    await user.click(confirmBtn);

    await waitFor(() => expect(screen.queryByText('design.pdf')).not.toBeInTheDocument());
  });

  it('cancel in confirm dialog does not delete', async () => {
    const user = userEvent.setup();
    render(<AttachmentList workItemId="wi1" canEdit={false} currentUserId="u1" />);
    await waitFor(() => expect(screen.getByText('design.pdf')).toBeInTheDocument());

    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    await user.click(deleteBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelBtn);

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('design.pdf')).toBeInTheDocument();
  });
});
