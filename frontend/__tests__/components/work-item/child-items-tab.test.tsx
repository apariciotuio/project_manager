import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ChildItemsTab } from '@/components/work-item/child-items-tab';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const PARENT_ITEM: WorkItemResponse = {
  id: 'parent-1',
  title: 'Parent Epic',
  type: 'initiative',
  state: 'draft',
  derived_state: null,
  owner_id: 'u1',
  creator_id: 'u1',
  project_id: null,
  description: null,
  priority: null,
  due_date: null,
  tags: [],
  completeness_score: 0,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

const WORK_ITEM: WorkItemResponse = {
  ...PARENT_ITEM,
  id: 'wi-1',
  title: 'Current Story',
  type: 'story',
  parent_work_item_id: 'parent-1',
};

const CHILD_ITEM: WorkItemResponse = {
  ...PARENT_ITEM,
  id: 'child-1',
  title: 'Child sub-item',
  type: 'task',
  parent_work_item_id: 'wi-1',
};

const TASKS_RESPONSE = {
  data: {
    nodes: [
      {
        id: 'n1',
        work_item_id: 'wi-1',
        parent_node_id: null,
        materialized_path: '',
        title: 'Setup',
        status: 'draft',
        position: 0,
      },
    ],
    edges: [],
  },
};

function setupHandlers(withParent = true, withChildren = true) {
  server.use(
    http.get('http://localhost/api/v1/work-items/wi-1/tasks', () =>
      HttpResponse.json(TASKS_RESPONSE),
    ),
    http.get('http://localhost/api/v1/work-items', ({ request }) => {
      const url = new URL(request.url);
      if (url.searchParams.get('parent_work_item_id') === 'wi-1') {
        return HttpResponse.json({
          data: {
            items: withChildren ? [CHILD_ITEM] : [],
            total: withChildren ? 1 : 0,
            page: 1,
            page_size: 50,
          },
        });
      }
      return HttpResponse.json({ data: { items: [], total: 0, page: 1, page_size: 50 } });
    }),
  );
  if (withParent) {
    server.use(
      http.get('http://localhost/api/v1/work-items/parent-1', () =>
        HttpResponse.json({ data: PARENT_ITEM }),
      ),
    );
  }
}

describe('ChildItemsTab', () => {
  it('renders breadcrumb when work item has a parent', async () => {
    setupHandlers(true);
    render(
      <ChildItemsTab workItemId="wi-1" workItem={WORK_ITEM} slug="ws1" />,
    );

    await screen.findByText('Parent Epic');
  });

  it('does not render breadcrumb when work item has no parent', async () => {
    setupHandlers(false);
    render(
      <ChildItemsTab
        workItemId="wi-1"
        workItem={{ ...WORK_ITEM, parent_work_item_id: null }}
        slug="ws1"
      />,
    );

    // Wait for loading to settle
    await waitFor(() =>
      expect(screen.queryByText('Parent Epic')).toBeNull(),
    );
  });

  it('renders sub-tasks section with TaskTree', async () => {
    setupHandlers(true);
    render(
      <ChildItemsTab workItemId="wi-1" workItem={WORK_ITEM} slug="ws1" />,
    );

    // Sub-tasks section heading
    await screen.findByText('Setup'); // task node title from tree
  });

  it('renders sub-items section with child work items', async () => {
    setupHandlers(true, true);
    render(
      <ChildItemsTab workItemId="wi-1" workItem={WORK_ITEM} slug="ws1" />,
    );

    await screen.findByText('Child sub-item');
  });

  it('parent breadcrumb link navigates to parent item page', async () => {
    setupHandlers(true);
    render(
      <ChildItemsTab workItemId="wi-1" workItem={WORK_ITEM} slug="ws1" />,
    );

    const link = await screen.findByRole('link', { name: /parent epic/i });
    expect(link.getAttribute('href')).toBe('/workspace/ws1/items/parent-1');
  });
});
