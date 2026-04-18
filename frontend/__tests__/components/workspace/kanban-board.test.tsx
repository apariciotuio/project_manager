/**
 * EP-09 — KanbanBoard component tests.
 * RED phase: tests written before implementation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import KanbanPage from '@/app/workspace/[slug]/kanban/page';

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams: Record<string, string> = {};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => '/workspace/acme/kanban',
  useParams: () => ({ slug: 'acme' }),
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams[key] ?? null,
    toString: () => '',
  }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'a@b.com',
      full_name: 'Test User',
      workspace_id: 'ws-1',
      workspace_slug: 'acme',
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
  }),
}));

const mockBoard = {
  group_by: 'state',
  columns: [
    {
      key: 'draft',
      label: 'Draft',
      total_count: 2,
      next_cursor: null,
      cards: [
        { id: 'wi-1', title: 'Card One', type: 'task', state: 'draft', owner_id: 'u1', completeness_score: 40, attachment_count: 0, tag_ids: [] },
        { id: 'wi-2', title: 'Card Two', type: 'bug', state: 'draft', owner_id: 'u1', completeness_score: 60, attachment_count: 2, tag_ids: ['tag-1'] },
      ],
    },
    {
      key: 'in_review',
      label: 'In review',
      total_count: 1,
      next_cursor: 'cursor-abc',
      cards: [
        { id: 'wi-3', title: 'Card Three', type: 'task', state: 'in_review', owner_id: 'u2', completeness_score: 80, attachment_count: 0, tag_ids: [] },
      ],
    },
    {
      key: 'ready',
      label: 'Ready',
      total_count: 0,
      next_cursor: null,
      cards: [],
    },
  ],
};

function setupKanbanHandler(data = mockBoard) {
  server.use(
    http.get('http://localhost/api/v1/work-items/kanban', () =>
      HttpResponse.json({ data, message: 'ok' }),
    ),
  );
}

describe('KanbanPage', () => {
  beforeEach(() => {
    mockSearchParams = {};
    mockPush.mockClear();
    mockReplace.mockClear();
    setupKanbanHandler();
  });

  it('renders loading skeleton initially', () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    expect(screen.getByTestId('kanban-skeleton')).toBeInTheDocument();
  });

  it('renders one KanbanColumn per column in response', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('kanban-column-draft')).toBeInTheDocument();
      expect(screen.getByTestId('kanban-column-in_review')).toBeInTheDocument();
      expect(screen.getByTestId('kanban-column-ready')).toBeInTheDocument();
    });
  });

  it('each column header shows label and total_count', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('kanban-column-draft')).toBeInTheDocument();
    });
    const draftCol = screen.getByTestId('kanban-column-draft');
    expect(draftCol).toHaveTextContent('Draft');
    expect(draftCol).toHaveTextContent('2');
  });

  it('cards render within their column', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByText('Card One')).toBeInTheDocument();
      expect(screen.getByText('Card Two')).toBeInTheDocument();
      expect(screen.getByText('Card Three')).toBeInTheDocument();
    });
  });

  it('"Load more" button visible when next_cursor is non-null', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('load-more-in_review')).toBeInTheDocument();
    });
  });

  it('"Load more" not visible when next_cursor is null', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.queryByTestId('load-more-draft')).not.toBeInTheDocument();
    });
  });

  it('shows error state on 5xx', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/kanban', () =>
        HttpResponse.json({ error: { message: 'Server error', code: 'INTERNAL', details: {} } }, { status: 500 }),
      ),
    );
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('kanban-error')).toBeInTheDocument();
    });
  });

  it('shows empty column state when column has zero cards', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('kanban-column-ready')).toBeInTheDocument();
    });
    // Ready column has 0 cards — shows empty placeholder
    expect(screen.getByTestId('kanban-column-ready')).toHaveTextContent('0');
  });

  it('card shows attachment icon when attachment_count > 0', async () => {
    render(<KanbanPage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByText('Card Two')).toBeInTheDocument();
    });
    // Card Two has attachment_count: 2
    expect(screen.getByTestId('attachment-count-wi-2')).toBeInTheDocument();
  });
});
