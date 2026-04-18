/**
 * EP-09 — QuickViewPanel tests.
 * RED phase: tests written before implementation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { QuickViewPanel } from '@/components/workspace/quick-view-panel';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => '/workspace/acme/items',
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockItem = {
  id: 'wi-1',
  title: 'Test Item',
  type: 'task',
  state: 'draft',
  derived_state: null,
  owner_id: 'u1',
  creator_id: 'u1',
  project_id: null,
  description: 'This is a test description',
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 65,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

function setupItemHandler(data = mockItem) {
  server.use(
    http.get('http://localhost/api/v1/work-items/:id', () =>
      HttpResponse.json({ data, message: 'ok' }),
    ),
  );
}

describe('QuickViewPanel', () => {
  beforeEach(() => {
    setupItemHandler();
    mockPush.mockClear();
  });

  it('is not rendered when itemId is null', () => {
    const { container } = render(<QuickViewPanel itemId={null} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('fetches and renders item title and state', async () => {
    render(<QuickViewPanel itemId="wi-1" onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('quick-view-title')).toHaveTextContent('Test Item');
    });
    expect(screen.getByTestId('quick-view-state')).toBeInTheDocument();
  });

  it('renders completeness score', async () => {
    render(<QuickViewPanel itemId="wi-1" onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('quick-view-completeness')).toBeInTheDocument();
    });
  });

  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn();
    render(<QuickViewPanel itemId="wi-1" onClose={onClose} />);
    await waitFor(() => {
      expect(screen.getByTestId('quick-view-panel')).toBeInTheDocument();
    });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when overlay/close button is clicked', async () => {
    const onClose = vi.fn();
    render(<QuickViewPanel itemId="wi-1" onClose={onClose} />);
    await waitFor(() => {
      expect(screen.getByTestId('quick-view-close')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByTestId('quick-view-close'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows error state on fetch failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/:id', () =>
        HttpResponse.json({ error: { message: 'Not found', code: 'NOT_FOUND', details: {} } }, { status: 404 }),
      ),
    );
    render(<QuickViewPanel itemId="wi-missing" onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('quick-view-error')).toBeInTheDocument();
    });
  });
});
