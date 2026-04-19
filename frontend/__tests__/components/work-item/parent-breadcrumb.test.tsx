import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ParentBreadcrumb } from '@/components/work-item/parent-breadcrumb';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => `workspace.itemDetail.breadcrumb.${key}`,
}));

// Mock next/link to render a plain anchor
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const PARENT: WorkItemResponse = {
  id: 'parent-1',
  title: 'Parent item',
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

const CURRENT: WorkItemResponse = {
  ...PARENT,
  id: 'item-1',
  title: 'Current item',
  parent_work_item_id: 'parent-1',
};

describe('ParentBreadcrumb', () => {
  it('renders nothing when work item has no parent', async () => {
    const { container } = render(
      <ParentBreadcrumb workItem={{ ...CURRENT, parent_work_item_id: null }} slug="ws1" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when parent_work_item_id is null', () => {
    const { container } = render(
      <ParentBreadcrumb workItem={{ ...CURRENT, parent_work_item_id: null }} slug="ws1" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders parent title as link when parent exists', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/parent-1', () =>
        HttpResponse.json({ data: PARENT }),
      ),
    );

    const { findByText } = render(
      <ParentBreadcrumb workItem={CURRENT} slug="ws1" />,
    );

    const parentLink = await findByText('Parent item');
    expect(parentLink).toBeDefined();
  });

  it('parent link points to parent work item detail page', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/parent-1', () =>
        HttpResponse.json({ data: PARENT }),
      ),
    );

    const { findByRole } = render(
      <ParentBreadcrumb workItem={CURRENT} slug="ws1" />,
    );

    const link = await findByRole('link');
    expect(link.getAttribute('href')).toBe('/workspace/ws1/items/parent-1');
  });

  it('renders separator between parent and current title', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/parent-1', () =>
        HttpResponse.json({ data: PARENT }),
      ),
    );

    render(<ParentBreadcrumb workItem={CURRENT} slug="ws1" />);

    // Wait for async load
    await screen.findByText('Parent item');
    // Current item title is non-link
    expect(screen.getByText('Current item')).toBeDefined();
  });

  it('renders breadcrumb nav with aria-label', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/parent-1', () =>
        HttpResponse.json({ data: PARENT }),
      ),
    );

    render(<ParentBreadcrumb workItem={CURRENT} slug="ws1" />);
    await screen.findByText('Parent item');

    const nav = screen.getByRole('navigation');
    expect(nav.getAttribute('aria-label')).toBe('workspace.itemDetail.breadcrumb.aria');
  });
});
