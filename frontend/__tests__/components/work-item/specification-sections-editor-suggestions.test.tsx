import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { SpecificationSectionsEditor } from '@/components/work-item/specification-sections-editor';
import { SplitViewContext } from '@/components/detail/split-view-context';
import type { SplitViewContextValue, PendingSuggestion } from '@/components/detail/split-view-context';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const BASE = 'http://localhost';

const SECTION_PROBLEM = {
  id: 'sec-1',
  work_item_id: 'wi-1',
  section_type: 'problem_statement',
  content: 'Original problem content',
  display_order: 1,
  is_required: true,
  generation_source: 'manual',
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by: 'user-1',
  updated_by: 'user-1',
};

const PENDING: PendingSuggestion = {
  section_type: 'problem_statement',
  proposed_content: 'Proposed new content',
  rationale: 'AI suggested this',
  received_at: Date.now(),
};

function setupSpecHandler(sections = [SECTION_PROBLEM]) {
  server.use(
    http.get(`${BASE}/api/v1/work-items/wi-1/specification`, () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', sections } }),
    ),
  );
}

function buildCtx(overrides: Partial<SplitViewContextValue> = {}): SplitViewContextValue {
  return {
    highlightedSectionId: null,
    setHighlightedSectionId: vi.fn(),
    pendingSuggestions: {},
    emitSuggestion: vi.fn(),
    clearSuggestion: vi.fn(),
    ...overrides,
  };
}

function renderWithCtx(ctx: SplitViewContextValue) {
  return render(
    <SplitViewContext.Provider value={ctx}>
      <SpecificationSectionsEditor workItemId="wi-1" canEdit={true} />
    </SplitViewContext.Provider>,
  );
}

// ---------------------------------------------------------------------------
// 5.1 Render pending suggestion
// ---------------------------------------------------------------------------

describe('SpecificationSectionsEditor — pending suggestion', () => {
  beforeEach(() => {
    setupSpecHandler();
  });

  it('no pending suggestion → editor renders normally, no card', async () => {
    const ctx = buildCtx({ pendingSuggestions: {} });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByDisplayValue('Original problem content')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('pending-suggestion-card')).not.toBeInTheDocument();
  });

  it('pending suggestion for section → card renders above textarea', async () => {
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING } });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );
  });

  it('Accept → patchSection called with proposed content; clearSuggestion called', async () => {
    const clearSuggestion = vi.fn();
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING }, clearSuggestion });

    server.use(
      http.patch(`${BASE}/api/v1/work-items/wi-1/sections/sec-1`, () =>
        HttpResponse.json({
          data: { ...SECTION_PROBLEM, content: 'Proposed new content', version: 2 },
        }),
      ),
    );

    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: /accept/i }));

    await waitFor(() => expect(clearSuggestion).toHaveBeenCalledWith('problem_statement'));
  });

  it('Reject → clearSuggestion called, no network call', async () => {
    const clearSuggestion = vi.fn();
    let patchCalled = false;
    server.use(
      http.patch(`${BASE}/api/v1/work-items/wi-1/sections/sec-1`, () => {
        patchCalled = true;
        return HttpResponse.json({ data: SECTION_PROBLEM });
      }),
    );

    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING }, clearSuggestion });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: /reject/i }));

    expect(clearSuggestion).toHaveBeenCalledWith('problem_statement');
    expect(patchCalled).toBe(false);
  });

  it('Edit → textarea value replaced; clearSuggestion called', async () => {
    const clearSuggestion = vi.fn();
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING }, clearSuggestion });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));

    await waitFor(() => {
      const textarea = screen.getByDisplayValue('Proposed new content');
      expect(textarea).toBeInTheDocument();
    });
    expect(clearSuggestion).toHaveBeenCalledWith('problem_statement');
  });

  it('canEdit=false → pending suggestion card not shown', async () => {
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING } });
    render(
      <SplitViewContext.Provider value={ctx}>
        <SpecificationSectionsEditor workItemId="wi-1" canEdit={false} />
      </SplitViewContext.Provider>,
    );

    await waitFor(() =>
      expect(screen.getByDisplayValue('Original problem content')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('pending-suggestion-card')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5.2 Conflict mode
// ---------------------------------------------------------------------------

describe('SpecificationSectionsEditor — conflict mode', () => {
  beforeEach(() => {
    setupSpecHandler();
  });

  it('user is typing (dirty buffer) + suggestion arrives → conflict banner renders', async () => {
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING } });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByDisplayValue('Original problem content')).toBeInTheDocument(),
    );

    // Simulate user typing (makes buffer dirty before the suggestion was visible)
    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.focus(ta);
    fireEvent.change(ta, { target: { value: 'User is editing right now' } });

    // Conflict mode: user focused + dirty buffer → card shows but in conflict mode
    await waitFor(() =>
      expect(screen.getByTestId('conflict-banner')).toBeInTheDocument(),
    );
  });

  it('conflict mode: click reveal → diff card becomes visible', async () => {
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING } });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByDisplayValue('Original problem content')).toBeInTheDocument(),
    );

    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.focus(ta);
    fireEvent.change(ta, { target: { value: 'User editing' } });

    await waitFor(() => expect(screen.getByTestId('conflict-banner')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('reveal-proposal-btn'));
    await waitFor(() => expect(screen.getByTestId('diff-hunk')).toBeInTheDocument());
  });

  it('suggestion absent when buffer is clean → no conflict banner', async () => {
    // No user edits; buffer equals section.content
    const ctx = buildCtx({ pendingSuggestions: { problem_statement: PENDING } });
    renderWithCtx(ctx);

    await waitFor(() =>
      expect(screen.getByTestId('pending-suggestion-card')).toBeInTheDocument(),
    );
    // No conflict banner when clean
    expect(screen.queryByTestId('conflict-banner')).not.toBeInTheDocument();
  });
});
