/**
 * FE-14-07 — TreeView component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TreeView } from '@/components/hierarchy/TreeView';
import type { WorkItemTreeNode, WorkItemSummary } from '@/lib/types/hierarchy';

function makeNode(id: string, title = `Item ${id}`, children: WorkItemTreeNode[] = []): WorkItemTreeNode {
  return { id, title, type: 'story', state: 'draft', parent_work_item_id: null, materialized_path: '', children };
}

function makeUnparented(id: string): WorkItemSummary {
  return { id, title: `Unparented ${id}`, type: 'task', state: 'draft', parent_work_item_id: null, materialized_path: '' };
}

const defaultMeta = { truncated: false, next_cursor: null };

describe('TreeView', () => {
  it('renders root nodes from roots array', () => {
    render(
      <TreeView
        roots={[makeNode('r1', 'Root One'), makeNode('r2', 'Root Two')]}
        unparented={[]}
        meta={defaultMeta}
        isLoading={false}
      />,
    );
    expect(screen.getByText('Root One')).toBeInTheDocument();
    expect(screen.getByText('Root Two')).toBeInTheDocument();
  });

  it('renders unparented section when unparented array is non-empty', () => {
    render(
      <TreeView
        roots={[]}
        unparented={[makeUnparented('u1')]}
        meta={defaultMeta}
        isLoading={false}
      />,
    );
    expect(screen.getAllByText(/unparented/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Unparented u1')).toBeInTheDocument();
  });

  it('collapses a root on toggle and hides its children', async () => {
    const root = makeNode('r1', 'Root', [makeNode('c1', 'Child')]);
    render(
      <TreeView roots={[root]} unparented={[]} meta={defaultMeta} isLoading={false} />,
    );
    // Expand first
    const expandBtn = screen.getByRole('button', { name: /expand/i });
    await userEvent.click(expandBtn);
    expect(screen.getByText('Child')).toBeInTheDocument();
    // Collapse
    const collapseBtn = screen.getByRole('button', { name: /collapse/i });
    await userEvent.click(collapseBtn);
    expect(screen.queryByText('Child')).not.toBeInTheDocument();
  });

  it('shows "Load more" button when meta.truncated = true', () => {
    render(
      <TreeView
        roots={[makeNode('r1')]}
        unparented={[]}
        meta={{ truncated: true, next_cursor: 'cursor-1' }}
        isLoading={false}
        onLoadMore={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
  });

  it('"Load more" button not shown when meta.truncated = false', () => {
    render(
      <TreeView
        roots={[makeNode('r1')]}
        unparented={[]}
        meta={defaultMeta}
        isLoading={false}
        onLoadMore={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
  });

  it('"Load more" triggers onLoadMore() callback', async () => {
    const onLoadMore = vi.fn();
    render(
      <TreeView
        roots={[makeNode('r1')]}
        unparented={[]}
        meta={{ truncated: true, next_cursor: 'c1' }}
        isLoading={false}
        onLoadMore={onLoadMore}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /load more/i }));
    expect(onLoadMore).toHaveBeenCalledOnce();
  });

  it('renders loading skeleton when isLoading = true', () => {
    render(
      <TreeView roots={[]} unparented={[]} meta={defaultMeta} isLoading={true} />,
    );
    expect(screen.getByTestId('tree-loading-skeleton')).toBeInTheDocument();
  });

  it('renders empty state when roots and unparented are both empty', () => {
    render(
      <TreeView roots={[]} unparented={[]} meta={defaultMeta} isLoading={false} />,
    );
    expect(screen.getByTestId('tree-empty-state')).toBeInTheDocument();
  });

  it('large tree (20+ nodes) renders via virtualizer container', () => {
    const roots = Array.from({ length: 20 }, (_, i) => makeNode(`r${i}`, `Root ${i}`));
    const { container } = render(
      <TreeView roots={roots} unparented={[]} meta={defaultMeta} isLoading={false} />,
    );
    // Virtualizer wraps content in a positioned container with a total size
    const virtualContainer = container.querySelector('[data-testid="tree-virtual-container"]');
    expect(virtualContainer).toBeInTheDocument();
  });
});
