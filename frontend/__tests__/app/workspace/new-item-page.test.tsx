import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

// ─── Mocks ────────────────────────────────────────────────────────────────────

// next-intl mock — DraftResumeBanner and StalenessWarning use useTranslations
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

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const TEMPLATES = [
  { id: 't1', name: 'Bug Report', description: null, type: 'bug', fields: {} },
  { id: 't2', name: 'Feature', description: 'Feature template', type: 'enhancement', fields: {} },
];

const PROJECTS = [
  { id: 'p1', name: 'Alpha', description: null, created_at: '2024-01-01' },
  { id: 'p2', name: 'Beta', description: null, created_at: '2024-01-02' },
];

const TAGS = [
  { id: 'tag1', name: 'frontend', color: '#3b82f6', archived: false, created_at: '2024-01-01' },
  { id: 'tag2', name: 'backend', color: '#10b981', archived: false, created_at: '2024-01-01' },
  { id: 'tag3', name: 'archived-tag', color: null, archived: true, created_at: '2024-01-01' },
];

const PARENT_ITEMS_INITIATIVE = {
  items: [
    {
      id: 'ini1', title: 'Q1 Initiative', type: 'initiative', state: 'draft',
      derived_state: null, owner_id: 'u1', creator_id: 'u1', project_id: 'p1',
      description: null, priority: null, due_date: null, tags: [],
      completeness_score: 0, has_override: false, override_justification: null,
      owner_suspended_flag: false, parent_work_item_id: null,
      created_at: '2024-01-01', updated_at: '2024-01-01', deleted_at: null,
    },
  ],
  total: 1, page: 1, page_size: 20,
};

const PARENT_ITEMS_MILESTONE = {
  items: [
    {
      id: 'ms1', title: 'Milestone A', type: 'milestone', state: 'draft',
      derived_state: null, owner_id: 'u1', creator_id: 'u1', project_id: 'p1',
      description: null, priority: null, due_date: null, tags: [],
      completeness_score: 0, has_override: false, override_justification: null,
      owner_suspended_flag: false, parent_work_item_id: null,
      created_at: '2024-01-01', updated_at: '2024-01-01', deleted_at: null,
    },
  ],
  total: 1, page: 1, page_size: 20,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function setupHandlers({
  draftData = null,
  projects = PROJECTS,
}: {
  draftData?: Record<string, unknown> | null;
  projects?: typeof PROJECTS;
} = {}) {
  server.use(
    http.get('http://localhost/api/v1/templates', () =>
      HttpResponse.json({ data: TEMPLATES }),
    ),
    http.get('http://localhost/api/v1/projects', () =>
      HttpResponse.json({ data: projects }),
    ),
    http.post('http://localhost/api/v1/projects', async ({ request }) => {
      const body = (await request.json()) as { name: string; description?: string };
      return HttpResponse.json({
        data: { id: 'p-new', name: body.name, description: body.description ?? null, created_at: '2024-01-01' },
      });
    }),
    http.get('http://localhost/api/v1/tags', () =>
      HttpResponse.json({ data: TAGS }),
    ),
    http.get('http://localhost/api/v1/work-items', ({ request }) => {
      const url = new URL(request.url);
      const type = url.searchParams.get('type');
      if (type === 'milestone') return HttpResponse.json({ data: PARENT_ITEMS_MILESTONE });
      return HttpResponse.json({ data: PARENT_ITEMS_INITIATIVE });
    }),
    http.get('http://localhost/api/v1/work-item-drafts', () =>
      HttpResponse.json({
        data: draftData
          ? {
              id: 'draft1',
              user_id: 'u1',
              workspace_id: 'ws1',
              data: draftData,
              local_version: 1,
              server_version: 1,
              updated_at: new Date().toISOString(),
            }
          : null,
      }),
    ),
    http.post('http://localhost/api/v1/work-item-drafts', () =>
      HttpResponse.json({ data: { draft_id: 'draft1', local_version: 2 } }),
    ),
    http.delete('http://localhost/api/v1/work-item-drafts/draft1', () =>
      new HttpResponse(null, { status: 204 }),
    ),
    http.post('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({
        data: {
          id: 'wi1',
          title: 'My item',
          type: 'task',
          state: 'draft',
          created_at: new Date().toISOString(),
        },
      }),
    ),
  );
}

async function importPage() {
  const { default: NewItemPage } = await import(
    /* @vite-ignore */
    '@/app/workspace/[slug]/items/new/page'
  );
  return NewItemPage;
}

/**
 * Radix Select renders an aria-hidden native <select> that we can use with
 * fireEvent.change to drive value changes without needing portal interaction.
 * We find it by its sibling relationship to the visible combobox trigger.
 */
function changeSelect(label: RegExp | string, value: string) {
  // All aria-hidden selects in the doc — find the one near the label
  const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
  // Pick the one with an option matching our value
  for (const sel of allSelects) {
    const opt = sel.querySelector(`option[value="${value}"]`);
    if (opt) {
      fireEvent.change(sel, { target: { value } });
      return;
    }
  }
  throw new Error(`No select found with option value="${value}" (label: ${String(label)})`);
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('NewItemPage', () => {
  beforeEach(() => {
    mockPush.mockReset();
  });

  it('renders the title input', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    expect(await screen.findByPlaceholderText(/título/i)).toBeTruthy();
  });

  it('renders templates after load', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByText('Bug Report')).toBeTruthy();
    });
  });

  it('create button is disabled when title is empty', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/título/i);
    const btn = screen.getByRole('button', { name: /crear/i });
    expect(btn).toBeDisabled();
  });

  // ─── Project picker ──────────────────────────────────────────────────────────

  it('renders project picker combobox', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    // Radix Select renders a combobox role for the trigger
    const trigger = await screen.findByRole('combobox', { name: /proyecto/i });
    expect(trigger).toBeTruthy();

    // The hidden native select has the options loaded from the hook
    await waitFor(() => {
      const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
      let found = false;
      for (const sel of allSelects) {
        if (sel.querySelector('option[value="p1"]')) found = true;
      }
      expect(found).toBe(true);
    });
  });

  it('shows inline "Crear proyecto" button when project list is empty', async () => {
    setupHandlers({ projects: [] });
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /crear proyecto/i })).toBeTruthy();
    });
  });

  it('create project dialog creates and auto-selects project', async () => {
    setupHandlers({ projects: [] });
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const createBtn = await screen.findByRole('button', { name: /crear proyecto/i });
    await userEvent.click(createBtn);

    const nameInput = await screen.findByPlaceholderText(/nombre del proyecto/i);
    await userEvent.type(nameInput, 'New Project');

    // Click confirm button in dialog (the Crear button that's not disabled)
    const allBtns = screen.getAllByRole('button', { name: /crear/i });
    const confirmBtn = allBtns.find((b) => !b.hasAttribute('disabled'));
    expect(confirmBtn).toBeTruthy();
    await userEvent.click(confirmBtn!);

    await waitFor(() => {
      // Dialog closes — name input gone
      expect(screen.queryByPlaceholderText(/nombre del proyecto/i)).toBeNull();
    });
  });

  // ─── Tag picker ──────────────────────────────────────────────────────────────

  it('renders tag chips for non-archived tags', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /frontend/i })).toBeTruthy();
      expect(screen.getByRole('button', { name: /backend/i })).toBeTruthy();
    });
    // Archived tag not shown
    expect(screen.queryByRole('button', { name: /archived-tag/i })).toBeNull();
  });

  it('toggles tag selection', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const frontendChip = await screen.findByRole('button', { name: /frontend/i });
    // Initially not pressed
    expect(frontendChip.getAttribute('aria-pressed')).toBe('false');

    await userEvent.click(frontendChip);
    expect(frontendChip.getAttribute('aria-pressed')).toBe('true');

    await userEvent.click(frontendChip);
    expect(frontendChip.getAttribute('aria-pressed')).toBe('false');
  });

  // ─── Parent picker ────────────────────────────────────────────────────────────

  it('parent picker is hidden for initiative type', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/título/i);

    // Default type is task (child type), so parent picker IS shown
    await waitFor(() => {
      expect(screen.getByLabelText(/padre/i)).toBeTruthy();
    });

    // Switch to initiative via hidden native select — parent picker should disappear
    changeSelect(/tipo/, 'initiative');

    await waitFor(() => {
      expect(screen.queryByLabelText(/padre/i)).toBeNull();
    });
  });

  it('parent picker appears only for child types (story)', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/título/i);

    // Switch to milestone — no parent picker
    changeSelect(/tipo/, 'milestone');
    await waitFor(() => {
      expect(screen.queryByLabelText(/padre/i)).toBeNull();
    });

    // Switch to story — parent picker appears
    changeSelect(/tipo/, 'story');
    await waitFor(() => {
      expect(screen.getByLabelText(/padre/i)).toBeTruthy();
    });
  });

  it('parent picker lists initiatives and milestones as options', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    await screen.findByPlaceholderText(/título/i);
    // task type is default — parent picker shown
    await waitFor(() => {
      expect(screen.getByLabelText(/padre/i)).toBeTruthy();
    });

    // After parent candidates load, they appear as options in the hidden select
    await waitFor(() => {
      const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
      let found = false;
      for (const sel of allSelects) {
        if (sel.querySelector('option[value="ini1"]') && sel.querySelector('option[value="ms1"]')) {
          found = true;
        }
      }
      expect(found).toBe(true);
    });
  });

  // ─── Draft resume banner ──────────────────────────────────────────────────────

  it('shows DraftResumeBanner when a server draft exists', async () => {
    setupHandlers({
      draftData: {
        title: 'Hydrated title',
        type: 'bug',
        description: 'Hydrated desc',
        project_id: 'p1',
        tags: ['frontend'],
      },
    });
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    // Banner appears once the draft is fetched
    await waitFor(() => {
      expect(screen.getByText('workspace.newItem.draft.resumeButton')).toBeTruthy();
    });
    // Form title is still empty — no auto-hydration
    const titleInput = screen.getByPlaceholderText(/título/i) as HTMLInputElement;
    expect(titleInput.value).toBe('');
  });

  it('draft hydration populates form when user clicks Resume', async () => {
    setupHandlers({
      draftData: {
        title: 'Hydrated title',
        type: 'bug',
        description: 'Hydrated desc',
        project_id: 'p1',
        tags: ['frontend'],
      },
    });
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    // Wait for banner
    const resumeBtn = await screen.findByText('workspace.newItem.draft.resumeButton');
    await userEvent.click(resumeBtn);

    await waitFor(() => {
      const titleInput = screen.getByPlaceholderText(/título/i) as HTMLInputElement;
      expect(titleInput.value).toBe('Hydrated title');
    });

    const descInput = screen.getByPlaceholderText(/descripción opcional/i) as HTMLTextAreaElement;
    expect(descInput.value).toBe('Hydrated desc');
  });

  it('discards server draft and keeps form blank when user clicks Discard', async () => {
    let deleteCalled = false;
    setupHandlers({
      draftData: { title: 'Old draft', type: 'task' },
    });
    server.use(
      http.delete('http://localhost/api/v1/work-item-drafts/draft1', () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const discardBtn = await screen.findByText('workspace.newItem.draft.discardButton');
    await userEvent.click(discardBtn);

    await waitFor(() => {
      // Banner gone
      expect(screen.queryByText('workspace.newItem.draft.resumeButton')).toBeNull();
    });
    expect(deleteCalled).toBe(true);
    // Form is still blank
    const titleInput = screen.getByPlaceholderText(/título/i) as HTMLInputElement;
    expect(titleInput.value).toBe('');
  });

  // ─── Draft save trigger ───────────────────────────────────────────────────────

  it('draft save is triggered after edits (debounced)', async () => {
    const draftSaveCalls: unknown[] = [];

    setupHandlers();
    // Override draft POST after setupHandlers so this handler takes priority
    server.use(
      http.post('http://localhost/api/v1/work-item-drafts', async ({ request }) => {
        const body = await request.json();
        draftSaveCalls.push(body);
        return HttpResponse.json({ data: { draft_id: 'draft1', local_version: 2 } });
      }),
    );

    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const titleInput = await screen.findByPlaceholderText(/título/i);
    await userEvent.type(titleInput, 'X');

    // Wait for 2s debounce + buffer
    await waitFor(
      () => {
        expect(draftSaveCalls.length).toBeGreaterThan(0);
      },
      { timeout: 6000 },
    );
  }, 8000);

  // ─── Submit ───────────────────────────────────────────────────────────────────

  it('submits work item with project_id and redirects', async () => {
    setupHandlers();
    const NewItemPage = await importPage();
    render(<NewItemPage params={{ slug: 'acme' }} />);

    const titleInput = await screen.findByPlaceholderText(/título/i);
    await userEvent.type(titleInput, 'My item');

    // Wait for projects to load, then select p1
    await waitFor(() => {
      const allSelects = document.querySelectorAll('select[aria-hidden="true"]');
      let found = false;
      for (const sel of allSelects) {
        if (sel.querySelector('option[value="p1"]')) { found = true; break; }
      }
      expect(found).toBe(true);
    }, { timeout: 3000 });

    changeSelect(/proyecto/, 'p1');

    // Create button becomes enabled once title + project set
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /^crear$/i });
      expect(btn).not.toBeDisabled();
    });

    const btn = screen.getByRole('button', { name: /^crear$/i });
    await userEvent.click(btn);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/workspace/acme/items/wi1');
    }, { timeout: 5000 });
  }, 15000);
});
