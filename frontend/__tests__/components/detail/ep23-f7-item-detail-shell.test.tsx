/**
 * EP-23 F-7 — Work item detail page redesign
 * RED phase: tests written before implementation
 *
 * Tests:
 * 1. Two-column layout renders chat (left) + template (right) by default
 * 2. Top navbar renders all available tabs with correct ARIA roles
 * 3. Tab switch: only right column swaps; chat state preserved
 * 4. Arrow key navigation between tabs
 * 5. Viewport <1024px: tabbed (Chat | Template) layout + top navbar visible
 * 6. No-template item: falls back with explicit notice
 * 7. Save/edit action group rendered in top navbar right side
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ItemDetailShell } from '@/components/detail/item-detail-shell';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

// Mock ChatPanel — tracks input draft to verify state preservation
vi.mock('@/components/clarification/chat-panel', () => ({
  ChatPanel: ({ workItemId }: { workItemId: string }) => (
    <div data-testid="chat-panel" data-work-item-id={workItemId}>
      <input data-testid="chat-input" placeholder="Type a message" />
    </div>
  ),
}));

// Mock tab content components
vi.mock('@/components/work-item/comments-tab', () => ({
  CommentsTab: () => <div data-testid="comments-tab-content">Comments</div>,
}));
vi.mock('@/components/work-item/reviews-tab', () => ({
  ReviewsTab: () => <div data-testid="reviews-tab-content">Reviews</div>,
}));
vi.mock('@/components/work-item/timeline-tab', () => ({
  TimelineTab: () => <div data-testid="timeline-tab-content">Timeline</div>,
}));
vi.mock('@/components/attachments/attachment-list', () => ({
  AttachmentList: () => <div data-testid="attachment-list">Attachments</div>,
}));
vi.mock('@/components/attachments/attachment-drop-zone', () => ({
  AttachmentDropZone: () => null,
}));
vi.mock('@/components/work-item/completeness-panel', () => ({
  CompletenessPanel: () => <div data-testid="completeness-panel">Completeness</div>,
}));
vi.mock('@/components/work-item/version-history-panel', () => ({
  VersionHistoryPanel: () => <div data-testid="version-history-panel">Version History</div>,
}));
vi.mock('@/components/work-item/specification-sections-editor', () => ({
  SpecificationSectionsEditor: () => <div data-testid="spec-sections-editor">Spec Editor</div>,
}));
vi.mock('@/components/work-item/child-items-tab', () => ({
  ChildItemsTab: () => <div data-testid="child-items-tab">Dependencies</div>,
}));
vi.mock('@/components/work-item/work-item-edit-modal', () => ({
  WorkItemEditModal: ({ open }: { open: boolean }) =>
    open ? <div data-testid="edit-modal">Edit Modal</div> : null,
}));
vi.mock('@/components/work-item/diff-viewer', () => ({
  DiffViewer: () => <div data-testid="diff-viewer">Diff</div>,
}));
vi.mock('@/components/domain/lock-badge', () => ({
  LockBadge: ({ locked }: { locked: boolean }) =>
    locked ? <span data-testid="lock-badge">Locked</span> : null,
}));

const WORK_ITEM: WorkItemResponse = {
  id: 'wi-1',
  title: 'My Feature Story',
  type: 'story',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: null,
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 65,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

function renderShell(overrides?: Partial<Parameters<typeof ItemDetailShell>[0]>) {
  return render(
    <ItemDetailShell
      workItem={WORK_ITEM}
      slug="acme"
      canEdit={true}
      latestVersionId={null}
      {...overrides}
    />,
  );
}

// ── 1. Two-column layout ──────────────────────────────────────────────────────

describe('ItemDetailShell — two-column layout (desktop ≥1024px)', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('renders chat panel on the left', () => {
    renderShell();
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
  });

  it('renders template (spec editor) on the right by default', () => {
    renderShell();
    expect(screen.getByTestId('spec-sections-editor')).toBeInTheDocument();
  });

  it('left and right columns are separate DOM containers', () => {
    renderShell();
    const chatPanel = screen.getByTestId('chat-panel');
    const specEditor = screen.getByTestId('spec-sections-editor');
    // They must not share the same direct parent
    expect(chatPanel.parentElement).not.toBe(specEditor.parentElement);
  });

  it('item title is rendered as <h1> in the template column', () => {
    renderShell();
    const h1 = screen.getByRole('heading', { level: 1, name: /My Feature Story/i });
    expect(h1).toBeInTheDocument();
  });
});

// ── 2. Top navbar / tablist ───────────────────────────────────────────────────

describe('ItemDetailShell — top navbar tabs', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('renders a tablist element', () => {
    renderShell();
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('Template tab is present and selected by default', () => {
    renderShell();
    const templateTab = screen.getByRole('tab', { name: /template/i });
    expect(templateTab).toBeInTheDocument();
    expect(templateTab).toHaveAttribute('aria-selected', 'true');
  });

  it('renders Comments, Reviews, Timeline, Adjuntos, Spec completeness tabs', () => {
    renderShell();
    expect(screen.getByRole('tab', { name: /comments|comentarios/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /reviews|revisiones/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /timeline|historial/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /adjuntos/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /spec|completeness|especificación/i })).toBeInTheDocument();
  });

  it('each tab has aria-controls pointing to its tabpanel', () => {
    renderShell();
    const tabs = screen.getAllByRole('tab');
    tabs.forEach((tab) => {
      const controlsId = tab.getAttribute('aria-controls');
      expect(controlsId).toBeTruthy();
      const panel = document.getElementById(controlsId!);
      expect(panel).toBeTruthy();
    });
  });

  it('each visible tabpanel has role=tabpanel and aria-labelledby', () => {
    renderShell();
    const panels = screen.getAllByRole('tabpanel');
    panels.forEach((panel) => {
      expect(panel).toHaveAttribute('aria-labelledby');
    });
  });
});

// ── 3. Tab switch — right column swaps, chat stays mounted ───────────────────

describe('ItemDetailShell — tab switching', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('clicking Comments tab shows comments content', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('tab', { name: /comments|comentarios/i }));
    expect(screen.getByTestId('comments-tab-content')).toBeInTheDocument();
  });

  it('clicking Reviews tab shows reviews content', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('tab', { name: /reviews|revisiones/i }));
    expect(screen.getByTestId('reviews-tab-content')).toBeInTheDocument();
  });

  it('chat panel remains mounted across tab switches', async () => {
    const user = userEvent.setup();
    renderShell();

    // Type in chat input
    const chatInput = screen.getByTestId('chat-input');
    await user.type(chatInput, 'hello world');
    expect(chatInput).toHaveValue('hello world');

    // Switch tab
    await user.click(screen.getByRole('tab', { name: /comments|comentarios/i }));

    // Chat panel still mounted (input still in DOM, value preserved)
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
    expect(screen.getByTestId('chat-input')).toHaveValue('hello world');
  });

  it('switching tabs updates aria-selected on active tab', async () => {
    const user = userEvent.setup();
    renderShell();

    const commentsTab = screen.getByRole('tab', { name: /comments|comentarios/i });
    await user.click(commentsTab);

    expect(commentsTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /template/i })).toHaveAttribute('aria-selected', 'false');
  });
});

// ── 4. Arrow key navigation ───────────────────────────────────────────────────

describe('ItemDetailShell — keyboard navigation', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('ArrowRight moves focus to next tab', () => {
    renderShell();
    const tablist = screen.getByRole('tablist');
    const tabs = screen.getAllByRole('tab');
    const firstTab = tabs[0];

    firstTab.focus();
    fireEvent.keyDown(tablist, { key: 'ArrowRight' });

    expect(document.activeElement).toBe(tabs[1]);
  });

  it('ArrowLeft moves focus to previous tab', () => {
    renderShell();
    const tablist = screen.getByRole('tablist');
    const tabs = screen.getAllByRole('tab');
    const secondTab = tabs[1];

    secondTab.focus();
    fireEvent.keyDown(tablist, { key: 'ArrowLeft' });

    expect(document.activeElement).toBe(tabs[0]);
  });

  it('ArrowRight wraps from last tab to first', () => {
    renderShell();
    const tablist = screen.getByRole('tablist');
    const tabs = screen.getAllByRole('tab');
    const lastTab = tabs[tabs.length - 1];

    lastTab.focus();
    fireEvent.keyDown(tablist, { key: 'ArrowRight' });

    expect(document.activeElement).toBe(tabs[0]);
  });
});

// ── 5. Responsive <1024px collapse ───────────────────────────────────────────

describe('ItemDetailShell — responsive layout <1024px', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 768 });
  });

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('top navbar (tablist) is still rendered on narrow viewport', () => {
    renderShell();
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('renders a mobile tab switcher (Chat | Template) on narrow viewport', () => {
    renderShell();
    // There should be mobile tabs for Chat and Template content switching
    const mobileChatTab = screen.getByRole('tab', { name: /^chat$/i });
    expect(mobileChatTab).toBeInTheDocument();
  });
});

// ── 6. No-template fallback ───────────────────────────────────────────────────

describe('ItemDetailShell — no-template fallback', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('shows explicit "No template" notice when item has no type template', () => {
    renderShell({ workItem: { ...WORK_ITEM, type: undefined as unknown as string } });
    expect(
      screen.getByText(/no template.*generic view|generic.*no template/i),
    ).toBeInTheDocument();
  });
});

// ── 7. Action group in top navbar ─────────────────────────────────────────────

describe('ItemDetailShell — action group', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1280 });
  });

  it('renders an Edit action button in the navbar when canEdit=true', () => {
    renderShell({ canEdit: true });
    expect(screen.getByRole('button', { name: /edit|editar/i })).toBeInTheDocument();
  });

  it('does not render Edit action when canEdit=false', () => {
    renderShell({ canEdit: false });
    expect(screen.queryByRole('button', { name: /edit|editar/i })).not.toBeInTheDocument();
  });
});
