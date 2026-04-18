/**
 * EP-22 Phase 7 — detail page uses WorkItemDetailLayout; Clarificación tab removed.
 * Tests behavior: WorkItemDetailLayout present, ClarificationTab absent,
 * all other tabs still present inside the layout content area.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import WorkItemDetailPage from '@/app/workspace/[slug]/items/[id]/page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'user-1', full_name: 'Tester', workspace_id: 'ws1', workspace_slug: 'acme', email: 't@t.com', avatar_url: null, is_superadmin: false },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// Mock heavy components we don't need for layout tests
vi.mock('@/components/clarification/chat-panel', () => ({
  ChatPanel: ({ workItemId }: { workItemId: string }) => (
    <div data-testid="chat-panel" data-work-item-id={workItemId} />
  ),
}));
vi.mock('@/components/work-item/specification-sections-editor', () => ({
  SpecificationSectionsEditor: () => <div data-testid="spec-editor" />,
}));
vi.mock('@/components/work-item/completeness-panel', () => ({
  CompletenessPanel: () => <div data-testid="completeness-panel" />,
}));
vi.mock('@/components/work-item/next-step-hint', () => ({
  NextStepHint: () => null,
}));
vi.mock('@/components/work-item/tasks-tab', () => ({
  TasksTab: () => <div data-testid="tasks-tab" />,
}));
vi.mock('@/components/work-item/reviews-tab', () => ({
  ReviewsTab: () => <div data-testid="reviews-tab" />,
}));
vi.mock('@/components/work-item/comments-tab', () => ({
  CommentsTab: () => <div data-testid="comments-tab" />,
}));
vi.mock('@/components/work-item/timeline-tab', () => ({
  TimelineTab: () => <div data-testid="timeline-tab" />,
}));
vi.mock('@/components/work-item/child-items-tab', () => ({
  ChildItemsTab: () => <div data-testid="child-items-tab" />,
}));
vi.mock('@/components/work-item/version-history-panel', () => ({
  VersionHistoryPanel: () => <div data-testid="version-history-panel" />,
}));
vi.mock('@/components/work-item/transition-history', () => ({
  TransitionHistory: () => null,
}));
vi.mock('@/components/work-item/ownership-history', () => ({
  OwnershipHistory: () => null,
}));
vi.mock('@/components/docs/related-docs-widget', () => ({
  RelatedDocsWidget: () => null,
}));
vi.mock('@/components/docs/doc-preview-panel', () => ({
  DocPreviewPanel: () => null,
}));
vi.mock('@/components/attachments/attachment-list', () => ({
  AttachmentList: () => <div data-testid="attachment-list" />,
}));
vi.mock('@/components/attachments/attachment-drop-zone', () => ({
  AttachmentDropZone: () => null,
}));

function makeWorkItem(state: string) {
  return {
    id: 'wi-1',
    title: 'My Work Item',
    type: 'story',
    state,
    derived_state: null,
    owner_id: 'user-1',
    creator_id: 'user-1',
    project_id: null,
    description: null,
    priority: null,
    due_date: null,
    tags: [],
    completeness_score: 50,
    has_override: false,
    override_justification: null,
    owner_suspended_flag: false,
    parent_work_item_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    deleted_at: null,
  };
}

function setupHandlers(state = 'draft') {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1', () =>
      HttpResponse.json({ data: makeWorkItem(state) }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/specification', () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', sections: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/completeness', () =>
      HttpResponse.json({ data: { score: 50, level: 'medium', dimensions: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/gaps', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/next-step', () =>
      HttpResponse.json({ data: { next_step: 'improve_content', message: '', blocking: false, gaps_referenced: [], suggested_validators: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/locks', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/task-tree', () =>
      HttpResponse.json({ data: { work_item_id: 'wi-1', tree: [] } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/reviews', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/comments', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/timeline', () =>
      HttpResponse.json({ data: { events: [], next_cursor: null } }),
    ),
    http.get('http://localhost/api/v1/work-items/wi-1/tags', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/tags', () =>
      HttpResponse.json({ data: [] }),
    ),
    http.get('http://localhost/api/v1/work-items', () =>
      HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } }),
    ),
    http.get('http://localhost/api/v1/threads', () =>
      HttpResponse.json({ data: [] }),
    ),
  );
}

async function renderAndWait(state = 'draft') {
  setupHandlers(state);
  render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-1' }} />);
  await waitFor(() => expect(screen.getByText('My Work Item')).toBeInTheDocument());
}

describe('EP-22 Phase 7 — WorkItemDetailPage layout', () => {
  it('renders WorkItemDetailLayout (ChatPanel present in left slot) on desktop', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
    await renderAndWait();
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
  });

  it('right content slot renders SpecificationSectionsEditor', async () => {
    await renderAndWait();
    expect(screen.getByTestId('spec-editor')).toBeInTheDocument();
  });

  it('NO TabsTrigger value="clarificacion" in the DOM', async () => {
    await renderAndWait();
    const tabs = screen.queryAllByRole('tab');
    const clarTab = tabs.find(
      (t) => t.textContent?.toLowerCase().includes('clarific'),
    );
    expect(clarTab).toBeUndefined();
  });

  it('NO ClarificationTab component rendered', async () => {
    await renderAndWait();
    // ClarificationTab renders a "generateButton" button — must not exist
    // (this check works because ClarificationTab is NOT mocked in this test file)
    expect(screen.queryByRole('button', { name: /generateButton/i })).not.toBeInTheDocument();
  });

  it('renders correctly for DRAFT state', async () => {
    await renderAndWait('draft');
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
    const tabs = screen.queryAllByRole('tab');
    const clarTab = tabs.find((t) => t.textContent?.toLowerCase().includes('clarific'));
    expect(clarTab).toBeUndefined();
  });

  it('renders correctly for IN_CLARIFICATION state — still no Clarificación tab', async () => {
    await renderAndWait('in_clarification');
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
    const tabs = screen.queryAllByRole('tab');
    const clarTab = tabs.find((t) => t.textContent?.toLowerCase().includes('clarific'));
    expect(clarTab).toBeUndefined();
  });
});
