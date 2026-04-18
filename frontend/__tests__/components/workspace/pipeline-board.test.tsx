/**
 * EP-09 — PipelineBoard component tests.
 * RED phase: tests written before implementation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import PipelinePage from '@/app/workspace/[slug]/pipeline/page';

const mockReplace = vi.fn();
let mockSearchParams: Record<string, string> = {};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  usePathname: () => '/workspace/acme/pipeline',
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
  columns: [
    {
      state: 'draft',
      count: 3,
      avg_age_days: 2.5,
      items: [
        { id: 'wi-1', title: 'Item 1', type: 'task', state: 'draft', owner_id: 'u1', completeness_score: 30 },
        { id: 'wi-2', title: 'Item 2', type: 'bug', state: 'draft', owner_id: 'u1', completeness_score: 60 },
      ],
    },
    {
      state: 'in_clarification',
      count: 1,
      avg_age_days: 1.0,
      items: [
        { id: 'wi-3', title: 'Item 3', type: 'task', state: 'in_clarification', owner_id: 'u2', completeness_score: 50 },
      ],
    },
    { state: 'in_review', count: 0, avg_age_days: 0, items: [] },
    { state: 'partially_validated', count: 0, avg_age_days: 0, items: [] },
    { state: 'ready', count: 0, avg_age_days: 0, items: [] },
  ],
  blocked_lane: [
    { id: 'wi-b1', title: 'Blocked Item', type: 'task', state: 'blocked', owner_id: 'u3', completeness_score: 10 },
  ],
};

function setupPipelineHandler(data = mockBoard) {
  server.use(
    http.get('http://localhost/api/v1/pipeline', () =>
      HttpResponse.json({ data, message: 'ok' }),
    ),
  );
}

describe('PipelinePage', () => {
  beforeEach(() => {
    mockSearchParams = {};
    mockReplace.mockClear();
    setupPipelineHandler();
  });

  it('renders loading skeleton initially', () => {
    render(<PipelinePage params={{ slug: 'acme' }} />);
    expect(screen.getByTestId('pipeline-skeleton')).toBeInTheDocument();
  });

  it('renders all FSM state columns after load', async () => {
    render(<PipelinePage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-column-draft')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-column-in_clarification')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-column-in_review')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-column-partially_validated')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-column-ready')).toBeInTheDocument();
    });
  });

  it('renders column with count and items', async () => {
    render(<PipelinePage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-column-draft')).toBeInTheDocument();
    });
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
  });

  it('renders blocked lane with blocked items', async () => {
    render(<PipelinePage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-blocked-lane')).toBeInTheDocument();
    });
    expect(screen.getByText('Blocked Item')).toBeInTheDocument();
  });

  it('renders amber aging badge for items with days_in_state > 7', async () => {
    const boardWithAging = {
      ...mockBoard,
      columns: [
        {
          state: 'draft',
          count: 1,
          avg_age_days: 10,
          items: [
            { id: 'wi-aging', title: 'Old Item', type: 'task', state: 'draft', owner_id: 'u1', completeness_score: 20 },
          ],
        },
        ...mockBoard.columns.slice(1),
      ],
    };
    server.use(
      http.get('http://localhost/api/v1/pipeline', () =>
        HttpResponse.json({ data: boardWithAging, message: 'ok' }),
      ),
    );
    render(<PipelinePage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-column-draft')).toBeInTheDocument();
    });
    // Column with avg_age_days 10 renders amber badge
    expect(screen.getByTestId('aging-badge-draft')).toBeInTheDocument();
    expect(screen.getByTestId('aging-badge-draft')).toHaveAttribute('data-severity', 'amber');
  });

  it('shows empty state when all columns have zero items', async () => {
    const emptyBoard = {
      columns: [
        { state: 'draft', count: 0, avg_age_days: 0, items: [] },
        { state: 'in_clarification', count: 0, avg_age_days: 0, items: [] },
        { state: 'in_review', count: 0, avg_age_days: 0, items: [] },
        { state: 'partially_validated', count: 0, avg_age_days: 0, items: [] },
        { state: 'ready', count: 0, avg_age_days: 0, items: [] },
      ],
      blocked_lane: [],
    };
    server.use(
      http.get('http://localhost/api/v1/pipeline', () =>
        HttpResponse.json({ data: emptyBoard, message: 'ok' }),
      ),
    );
    render(<PipelinePage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-empty-state')).toBeInTheDocument();
    });
  });

  it('shows error state on 5xx', async () => {
    server.use(
      http.get('http://localhost/api/v1/pipeline', () =>
        HttpResponse.json({ error: { message: 'Server error', code: 'INTERNAL', details: {} } }, { status: 500 }),
      ),
    );
    render(<PipelinePage params={{ slug: 'acme' }} />);
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-error')).toBeInTheDocument();
    });
  });
});
