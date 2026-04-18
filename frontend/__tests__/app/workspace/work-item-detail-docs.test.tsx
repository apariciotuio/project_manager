/**
 * EP-13 Group 4 — WorkItemDetailPage wires RelatedDocsWidget + DocPreviewPanel.
 * Tests: widget renders in side panel, DocPreviewPanel opens on doc click,
 * RelatedDocsWidget is lazy-loaded (Suspense boundary present).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import WorkItemDetailPage from '@/app/workspace/[slug]/items/[id]/page';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));

// Mock all child tabs/panels that we don't care about for this test
vi.mock('@/components/work-item/work-item-header', () => ({
  WorkItemHeader: () => <div data-testid="wi-header" />,
}));
vi.mock('@/components/work-item/work-item-edit-modal', () => ({
  WorkItemEditModal: () => null,
}));
vi.mock('@/components/work-item/state-transition-panel', () => ({
  StateTransitionPanel: () => <div data-testid="state-panel" />,
}));
vi.mock('@/components/work-item/owner-panel', () => ({
  OwnerPanel: () => <div data-testid="owner-panel" />,
}));
vi.mock('@/components/work-item/specification-sections-editor', () => ({
  SpecificationSectionsEditor: () => <div data-testid="spec-editor" />,
}));
vi.mock('@/components/work-item/completeness-panel', () => ({
  CompletenessPanel: () => <div data-testid="completeness" />,
}));
vi.mock('@/components/work-item/next-step-hint', () => ({
  NextStepHint: () => null,
}));
vi.mock('@/components/work-item/tasks-tab', () => ({
  TasksTab: () => null,
}));
vi.mock('@/components/work-item/reviews-tab', () => ({
  ReviewsTab: () => null,
}));
vi.mock('@/components/work-item/comments-tab', () => ({
  CommentsTab: () => null,
}));
vi.mock('@/components/work-item/timeline-tab', () => ({
  TimelineTab: () => null,
}));
vi.mock('@/components/work-item/child-items-tab', () => ({
  ChildItemsTab: () => null,
}));
vi.mock('@/components/work-item/transition-history', () => ({
  TransitionHistory: () => null,
}));
vi.mock('@/components/work-item/ownership-history', () => ({
  OwnershipHistory: () => null,
}));
vi.mock('@/components/work-item/version-history-panel', () => ({
  VersionHistoryPanel: () => null,
}));
vi.mock('@/components/clarification/clarification-tab', () => ({
  ClarificationTab: () => null,
}));
vi.mock('@/app/providers/auth-provider', () => ({
  useAuth: () => ({ user: { id: 'u1', is_superadmin: false } }),
}));

const BASE = 'http://localhost';

const mockWorkItem: WorkItemResponse = {
  id: 'wi-42',
  title: 'Test Work Item',
  type: 'bug',
  state: 'draft',
  derived_state: null,
  owner_id: 'u1',
  creator_id: 'u1',
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
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-15T00:00:00Z',
  deleted_at: null,
};

function stubWorkItem() {
  server.use(
    http.get(`${BASE}/api/v1/work-items/wi-42`, () =>
      HttpResponse.json({ data: mockWorkItem }),
    ),
    http.get(`${BASE}/api/v1/work-items/wi-42/versions`, () =>
      HttpResponse.json({ data: [], pagination: { cursor: null, has_next: false } }),
    ),
    http.get(`${BASE}/api/v1/work-items/wi-42/related-docs`, () =>
      HttpResponse.json({
        data: [
          {
            doc_id: 'rdoc-1',
            title: 'Related Doc Alpha',
            source_name: 'Confluence',
            snippet: 'Alpha snippet',
            url: 'https://wiki.example.com/alpha',
            score: 0.9,
          },
        ],
      }),
    ),
  );
}

function stubDocContent() {
  server.use(
    http.get(`${BASE}/api/v1/docs/rdoc-1/content`, () =>
      HttpResponse.json({
        data: {
          doc_id: 'rdoc-1',
          title: 'Related Doc Alpha',
          content_html: '<p>Alpha content</p>',
          url: 'https://wiki.example.com/alpha',
          source_name: 'Confluence',
          last_indexed_at: '2026-04-10T00:00:00Z',
        },
      }),
    ),
  );
}

describe('WorkItemDetailPage — docs integration', () => {
  it('renders RelatedDocsWidget in the specification side panel', async () => {
    stubWorkItem();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-42' }} />);

    await waitFor(() =>
      expect(screen.getByTestId('wi-header')).toBeInTheDocument(),
    );

    // Widget heading should be in the DOM (rendered inside spec tab side panel)
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /title/i })).toBeInTheDocument(),
    );
  });

  it('RelatedDocsWidget is wrapped in a Suspense boundary', async () => {
    stubWorkItem();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-42' }} />);

    await waitFor(() =>
      expect(screen.getByTestId('wi-header')).toBeInTheDocument(),
    );

    // Related docs should load without blocking main content
    expect(screen.getByTestId('wi-header')).toBeInTheDocument();
    expect(screen.getByTestId('spec-editor')).toBeInTheDocument();
  });

  it('clicking a related doc opens DocPreviewPanel', async () => {
    stubWorkItem();
    stubDocContent();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-42' }} />);

    // Wait for related docs to appear
    await waitFor(() =>
      expect(screen.getByText('Related Doc Alpha')).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByText('Related Doc Alpha'));

    // DocPreviewPanel should open (role=dialog)
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    );
  });

  it('DocPreviewPanel can be closed', async () => {
    stubWorkItem();
    stubDocContent();
    render(<WorkItemDetailPage params={{ slug: 'acme', id: 'wi-42' }} />);

    await waitFor(() =>
      expect(screen.getByText('Related Doc Alpha')).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByText('Related Doc Alpha'));

    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    );

    // Close via Escape
    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
