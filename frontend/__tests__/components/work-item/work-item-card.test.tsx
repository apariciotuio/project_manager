import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkItemCard } from '@/components/work-item/work-item-card';
import type { WorkItemResponse } from '@/lib/types/work-item';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockItem: WorkItemResponse = {
  id: 'wi-1',
  title: 'Fix the login bug',
  type: 'bug',
  state: 'in_review',
  derived_state: null,
  owner_id: 'user-1',
  creator_id: 'user-1',
  project_id: 'proj-1',
  description: null,
  priority: 'high',
  due_date: null,
  tags: [],
  completeness_score: 65,
  has_override: false,
  override_justification: null,
  owner_suspended_flag: false,
  parent_work_item_id: null,
  created_at: '2026-04-15T00:00:00Z',
  updated_at: '2026-04-15T10:00:00Z',
  deleted_at: null,
  external_jira_key: null,
};

describe('WorkItemCard', () => {
  it('renders title as a link to the detail page', () => {
    render(<WorkItemCard workItem={mockItem} slug="acme" />);
    const link = screen.getByRole('link', { name: /fix the login bug/i });
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-1');
  });

  it('renders TypeBadge for the work item type', () => {
    render(<WorkItemCard workItem={mockItem} slug="acme" />);
    // TypeBadge renders with aria-label "Tipo: X"
    const badge = screen.getByRole('img', { name: /tipo/i });
    expect(badge).toBeInTheDocument();
  });

  it('renders StateBadge for the work item state', () => {
    render(<WorkItemCard workItem={mockItem} slug="acme" />);
    // StateBadge renders with role="status" and aria-label "Estado: X"
    const badge = screen.getByRole('status', { name: /estado/i });
    expect(badge).toBeInTheDocument();
  });

  it('renders CompletenessBar with the correct score', () => {
    render(<WorkItemCard workItem={mockItem} slug="acme" />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '65');
  });

  it('renders owner display name when provided', () => {
    render(<WorkItemCard workItem={mockItem} slug="acme" ownerDisplayName="Ada Lovelace" />);
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
  });

  it('omits owner section when ownerDisplayName is not provided', () => {
    render(<WorkItemCard workItem={mockItem} slug="acme" />);
    expect(screen.queryByTestId('work-item-card-owner')).toBeNull();
  });

  it('links correctly for a different slug', () => {
    render(<WorkItemCard workItem={{ ...mockItem, id: 'wi-99' }} slug="beta-corp" />);
    const link = screen.getByRole('link', { name: /fix the login bug/i });
    expect(link).toHaveAttribute('href', '/workspace/beta-corp/items/wi-99');
  });
});
