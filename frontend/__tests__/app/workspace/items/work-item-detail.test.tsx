import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import WorkItemDetailPage from '@/app/workspace/[slug]/items/[id]/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const WORK_ITEM = {
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
  completeness_score: 45,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
};

const SPEC = {
  sections: [
    {
      id: 'sec-1',
      section_type: 'problem_statement',
      content: 'Login fails on mobile',
      order: 0,
      is_required: true,
      last_updated_at: null,
      last_updated_by: null,
    },
  ],
};

const COMPLETENESS = {
  score: 45,
  level: 'medium',
  dimensions: [{ name: 'problem', score: 70, weight: 0.3, label: 'Problema' }],
};

function setupHandlers() {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1', () =>
      HttpResponse.json({ data: WORK_ITEM })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
      HttpResponse.json({ data: SPEC })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/completeness', () =>
      HttpResponse.json({ data: COMPLETENESS })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/gaps', () =>
      HttpResponse.json({ data: [] })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/locks', () =>
      HttpResponse.json({ data: [] })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/task-tree', () =>
      HttpResponse.json({ data: [] })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/reviews', () =>
      HttpResponse.json({ data: [] })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
      HttpResponse.json({ data: [] })
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
      HttpResponse.json({ data: [], total: 0, page: 1, page_size: 20 })
    )
  );
}

describe('WorkItemDetailPage', () => {
  it('shows loading skeleton initially', () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1', async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      })
    );
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);
    expect(document.querySelector('[aria-busy="true"]')).toBeTruthy();
  });

  it('renders title and type after load', async () => {
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => expect(screen.getByText('Fix login bug')).toBeInTheDocument());
    expect(screen.getByLabelText('Tipo: Error')).toBeInTheDocument();
  });

  it('shows tab navigation with Spanish labels', async () => {
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));

    expect(screen.getByRole('tab', { name: 'Especificación' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Tareas' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Revisiones' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Comentarios' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Historial' })).toBeInTheDocument();
  });

  it('default tab is Especificación and shows section content', async () => {
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));

    // Specification tab is active by default — section content visible
    await waitFor(() =>
      expect(screen.getByDisplayValue('Login fails on mobile')).toBeInTheDocument()
    );
  });

  it('shows error when work item fails to load', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1', () =>
        HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Not found' } },
          { status: 404 }
        )
      )
    );
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument()
    );
  });

  it('switches to Tareas tab', async () => {
    setupHandlers();
    const user = userEvent.setup();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));

    await user.click(screen.getByRole('tab', { name: 'Tareas' }));

    // Tasks tab content visible
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Tareas', selected: true })).toBeInTheDocument()
    );
  });

  it('shows completeness score in header', async () => {
    setupHandlers();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);

    await waitFor(() => screen.getByText('Fix login bug'));
    expect(screen.getByLabelText('Completitud: 45%')).toBeInTheDocument();
  });
});
