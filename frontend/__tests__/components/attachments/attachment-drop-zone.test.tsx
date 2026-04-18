import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AttachmentDropZone } from '@/components/attachments/attachment-drop-zone';

// Mock toast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

const ALLOWED_TYPES = ['image/*', 'application/pdf', 'text/plain'];
const MAX_SIZE = 20 * 1024 * 1024; // 20 MB

function makeFile(name: string, type: string, sizeBytes: number): File {
  const file = new File(['x'.repeat(Math.min(sizeBytes, 10))], name, { type });
  Object.defineProperty(file, 'size', { value: sizeBytes });
  return file;
}

describe('AttachmentDropZone', () => {
  beforeEach(() => {
    mockToast.mockClear();
  });

  it('renders drop area with accessible label', () => {
    render(<AttachmentDropZone disabled={false} />);
    expect(screen.getByRole('button', { name: /drag.*drop|select file|attach/i })).toBeInTheDocument();
  });

  it('applies drag-over highlight on dragover', () => {
    render(<AttachmentDropZone disabled={false} />);
    const zone = screen.getByTestId('attachment-drop-zone');
    fireEvent.dragOver(zone);
    expect(zone).toHaveAttribute('data-dragover', 'true');
  });

  it('removes drag-over highlight on dragleave', () => {
    render(<AttachmentDropZone disabled={false} />);
    const zone = screen.getByTestId('attachment-drop-zone');
    fireEvent.dragOver(zone);
    fireEvent.dragLeave(zone);
    expect(zone).toHaveAttribute('data-dragover', 'false');
  });

  it('shows upload-blocked toast on valid file drop — does NOT call any upload', async () => {
    render(<AttachmentDropZone disabled={false} />);
    const zone = screen.getByTestId('attachment-drop-zone');
    const file = makeFile('doc.pdf', 'application/pdf', 1024);

    fireEvent.drop(zone, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => expect(mockToast).toHaveBeenCalledOnce());
    const call = mockToast.mock.calls[0][0];
    expect(call.title ?? call.description).toMatch(/not yet available|pending/i);
  });

  it('rejects file exceeding 20 MB — shows validation error, no toast for blocked upload', async () => {
    render(<AttachmentDropZone disabled={false} />);
    const zone = screen.getByTestId('attachment-drop-zone');
    const bigFile = makeFile('huge.pdf', 'application/pdf', MAX_SIZE + 1);

    fireEvent.drop(zone, {
      dataTransfer: { files: [bigFile] },
    });

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('alert')).toHaveTextContent(/20\s*MB|too large/i);
    // upload-blocked toast must NOT fire for invalid files
    expect(mockToast).not.toHaveBeenCalled();
  });

  it('rejects disallowed MIME type — shows validation error', async () => {
    render(<AttachmentDropZone disabled={false} />);
    const zone = screen.getByTestId('attachment-drop-zone');
    const file = makeFile('virus.exe', 'application/x-msdownload', 1024);

    fireEvent.drop(zone, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('alert')).toHaveTextContent(/not allowed|invalid type/i);
  });

  it('shows upload-blocked toast when valid file selected via file input', async () => {
    const user = userEvent.setup();
    render(<AttachmentDropZone disabled={false} />);
    const input = screen.getByTestId('attachment-file-input') as HTMLInputElement;

    const file = makeFile('report.txt', 'text/plain', 512);
    await user.upload(input, file);

    await waitFor(() => expect(mockToast).toHaveBeenCalledOnce());
    const call = mockToast.mock.calls[0][0];
    expect(call.title ?? call.description).toMatch(/not yet available|pending/i);
  });

  it('is disabled when disabled prop is true', () => {
    render(<AttachmentDropZone disabled={true} />);
    const zone = screen.getByTestId('attachment-drop-zone');
    expect(zone).toHaveAttribute('aria-disabled', 'true');
  });
});
