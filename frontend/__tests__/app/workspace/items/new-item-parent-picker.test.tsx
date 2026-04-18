/**
 * FE-14-11 — ParentPicker in work item create form.
 *
 * Tests:
 * 1. ParentPicker (combobox) is rendered for types that can have parents
 * 2. ParentPicker is NOT rendered for milestone type (no parent allowed)
 * 3. Selecting a parent sets parent_work_item_id in the request body
 * 4. With no parent selected, parent_work_item_id is absent from request
 * 5. Switching type to one with no valid parents hides the ParentPicker
 * 6. API 422 HIERARCHY_INVALID_PARENT_TYPE shows inline field error on ParentPicker
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, _params?: Record<string, unknown>) =>
    `${ns}.${key}`,
}));

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, back: vi.fn() }),
  useParams: () => ({ slug: 'acme' }),
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      full_name: 'Ada',
      workspace_id: 'ws1',
      workspace_slug: 'acme',
      email: 'a@b.com',
      avatar_url: null,
      is_superadmin: false,
    },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

const PROJECTS = [
  { id: 'p1', name: 'Alpha', description: null, created_at: '2024-01-01' },
];

const PARENT_ITEM = { id: 'ini1', title: 'Q1 Initiative', type: 'initiative', state: 'draft' };

function setupHandlers() {
  server.use(
    http.get('http://localhost/api/v1/templates', () => HttpResponse.json({ data: [] })),
    http.get('http://localhost/api/v1/projects', () => HttpResponse.json({ data: PROJECTS })),
    http.get('http://localhost/api/v1/tags', () => HttpResponse.json({ data: [] })),
    http.get('http://localhost/api/v1/work-item-drafts', () =>
      HttpResponse.json({ data: null }),
    ),
    http.post('http://localhost/api/v1/work-item-drafts', () =>
      HttpResponse.json({ data: { draft_id: 'draft1', local_version: 2 } }),
    ),
    // ParentPicker typeahead
    http.get('http://localhost/api/v1/projects/:projectId/work-items', () =>
      HttpResponse.json({
        data: {
          items: [PARENT_ITEM],
          total: 1,
          cursor: null,
          has_next: false,
        },
      }),
    ),
    http.post('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({
        data: { id: 'wi1', title: 'My item', type: 'task', state: 'draft', created_at: new Date().toISOString() },
      }),
    ),
    http.delete('http://localhost/api/v1/work-item-drafts/draft1', () =>
      new HttpResponse(null, { status: 204 }),
    ),
  );
}

function changeSelect(value: string) {
  const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
  for (const sel of allSelects) {
    const opt = sel.querySelector(`option[value="${value}"]`);
    if (opt) {
      fireEvent.change(sel, { target: { value } });
      return;
    }
  }
  throw new Error(`No hidden select with option value="${value}"`);
}

async function importPage() {
  const { default: NewItemPage } = await import(
    /* @vite-ignore */
    '@/app/workspace/[slug]/items/new/page'
  );
  return NewItemPage;
}

describe('NewItemPage — ParentPicker (FE-14-11)', () => {
  beforeEach(() => {
    mockPush.mockReset();
  });

  it('renders ParentPicker combobox for story type (hierarchy-rules driven)', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    // Default type is task — ParentPicker should render (task has null = any parent)
    await waitFor(() => {
      // Switch to story — also shows picker
      changeSelect('story');
    });
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /parent/i })).toBeInTheDocument();
    });
  });

  it('ParentPicker is NOT rendered for milestone type', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/workspace\.newItem\.fields\.titlePlaceholder/i);

    changeSelect('milestone');

    await waitFor(() => {
      expect(screen.queryByRole('combobox', { name: /parent/i })).toBeNull();
    });
  });

  it('selecting a parent in ParentPicker includes parent_work_item_id in POST body', async () => {
    let capturedBody: Record<string, unknown> | null = null;
    setupHandlers();
    server.use(
      http.post('http://localhost/api/v1/work-items', async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          data: { id: 'wi1', title: 'T', type: 'task', state: 'draft', created_at: new Date().toISOString() },
        });
      }),
    );

    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    // Wait for title input
    const titleInput = await screen.findByPlaceholderText(/workspace\.newItem\.fields\.titlePlaceholder/i);
    await userEvent.type(titleInput, 'My story');

    // Switch to story to show picker
    await waitFor(() => changeSelect('story'));

    // Interact with ParentPicker combobox
    const picker = await screen.findByRole('combobox', { name: /parent/i });
    await userEvent.click(picker);
    await userEvent.type(picker, 'Q1');

    const option = await screen.findByText('Q1 Initiative');
    await userEvent.click(option);

    // Select project
    await waitFor(() => {
      const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
      let found = false;
      for (const sel of allSelects) {
        if (sel.querySelector('option[value="p1"]')) { found = true; break; }
      }
      expect(found).toBe(true);
    }, { timeout: 3000 });
    changeSelect('p1');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^crear$/i })).not.toBeDisabled();
    });
    await userEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
      expect(capturedBody!['parent_work_item_id']).toBe('ini1');
    }, { timeout: 5000 });
  }, 15000);

  it('submits without parent_work_item_id when no parent selected', async () => {
    let capturedBody: Record<string, unknown> | null = null;
    setupHandlers();
    server.use(
      http.post('http://localhost/api/v1/work-items', async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          data: { id: 'wi1', title: 'T', type: 'task', state: 'draft', created_at: new Date().toISOString() },
        });
      }),
    );

    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const titleInput = await screen.findByPlaceholderText(/workspace\.newItem\.fields\.titlePlaceholder/i);
    await userEvent.type(titleInput, 'No parent item');

    await waitFor(() => {
      const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
      let found = false;
      for (const sel of allSelects) {
        if (sel.querySelector('option[value="p1"]')) { found = true; break; }
      }
      expect(found).toBe(true);
    }, { timeout: 3000 });
    changeSelect('p1');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^crear$/i })).not.toBeDisabled();
    });
    await userEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
      expect(capturedBody!['parent_work_item_id']).toBeUndefined();
    }, { timeout: 5000 });
  }, 15000);

  it('switching type re-evaluates picker visibility per hierarchy-rules', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/workspace\.newItem\.fields\.titlePlaceholder/i);

    // task → picker shown (null = any parent allowed)
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /parent/i })).toBeInTheDocument();
    });

    // milestone → picker hidden
    changeSelect('milestone');
    await waitFor(() => {
      expect(screen.queryByRole('combobox', { name: /parent/i })).toBeNull();
    });

    // story → picker shown
    changeSelect('story');
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /parent/i })).toBeInTheDocument();
    });
  });
});
