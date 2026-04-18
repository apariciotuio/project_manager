import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkItemList } from '@/components/work-item/work-item-list';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockItem: WorkItemResponse = {
  id: 'wi-1',
  title: 'Build the rocket',
  type: 'task',
  state: 'draft',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 50,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-04-15T00:00:00Z',
  updated_at: '2026-04-15T10:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

describe('WorkItemList', () => {
  it('renders skeleton when isLoading is true', () => {
    render(<WorkItemList items={[]} slug="acme" isLoading />);
    expect(document.querySelector('[data-testid="work-items-skeleton"]')).toBeInTheDocument();
    expect(screen.queryByRole('list')).toBeNull();
  });

  it('does not render skeleton after loading', () => {
    render(<WorkItemList items={[mockItem]} slug="acme" isLoading={false} />);
    expect(document.querySelector('[data-testid="work-items-skeleton"]')).toBeNull();
  });

  it('renders error alert when error is provided', () => {
    const err = new Error('Network failure');
    render(<WorkItemList items={[]} slug="acme" error={err} />);
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain('Network failure');
  });

  it('does not render the list when error is provided', () => {
    const err = new Error('boom');
    render(<WorkItemList items={[]} slug="acme" error={err} />);
    expect(screen.queryByRole('list')).toBeNull();
  });

  it('renders emptyState when items is empty and no error', () => {
    render(
      <WorkItemList
        items={[]}
        slug="acme"
        emptyState={<p>No items here</p>}
      />,
    );
    expect(screen.getByText('No items here')).toBeInTheDocument();
    expect(screen.queryByRole('list')).toBeNull();
  });

  it('renders one list item per work item', () => {
    const items = [
      mockItem,
      { ...mockItem, id: 'wi-2', title: 'Land the rocket' },
    ];
    render(<WorkItemList items={items} slug="acme" />);
    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('renders each item title as a link to the detail page', () => {
    render(<WorkItemList items={[mockItem]} slug="acme" />);
    const link = screen.getByRole('link', { name: /build the rocket/i });
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-1');
  });

  it('renders nothing when items empty and no emptyState provided', () => {
    const { container } = render(<WorkItemList items={[]} slug="acme" />);
    expect(container.firstChild).toBeNull();
  });
});
