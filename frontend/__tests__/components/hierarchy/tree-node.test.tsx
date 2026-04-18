/**
 * FE-14-06 — TreeNode component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TreeNode } from '@/components/hierarchy/TreeNode';
import type { WorkItemTreeNode } from '@/lib/types/hierarchy';

function makeNode(overrides: Partial<WorkItemTreeNode> = {}): WorkItemTreeNode {
  return {
    id: 'n1',
    title: 'Node Title',
    type: 'story',
    state: 'draft',
    parent_work_item_id: null,
    materialized_path: '',
    children: [],
    ...overrides,
  };
}

describe('TreeNode', () => {
  it('renders item title', () => {
    render(<TreeNode node={makeNode()} depth={0} isExpanded={false} onToggle={vi.fn()} />);
    expect(screen.getByText('Node Title')).toBeInTheDocument();
  });

  it('renders type badge', () => {
    render(<TreeNode node={makeNode({ type: 'milestone' })} depth={0} isExpanded={false} onToggle={vi.fn()} />);
    expect(screen.getByText(/milestone/i)).toBeInTheDocument();
  });

  it('renders state badge', () => {
    render(<TreeNode node={makeNode({ state: 'ready' })} depth={0} isExpanded={false} onToggle={vi.fn()} />);
    expect(screen.getByText(/ready/i)).toBeInTheDocument();
  });

  it('renders RollupBadge when rollup_percent is provided', () => {
    render(
      <TreeNode
        node={makeNode()}
        depth={0}
        isExpanded={false}
        onToggle={vi.fn()}
        rollup_percent={75}
      />,
    );
    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveTextContent('75%');
  });

  it('does not render RollupBadge when rollup_percent is null', () => {
    render(
      <TreeNode node={makeNode()} depth={0} isExpanded={false} onToggle={vi.fn()} rollup_percent={null} />,
    );
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('shows expand/collapse toggle when children exist', () => {
    const node = makeNode({ children: [makeNode({ id: 'c1', title: 'Child' })] });
    render(<TreeNode node={node} depth={0} isExpanded={false} onToggle={vi.fn()} />);
    expect(screen.getByRole('button', { name: /expand|collapse/i })).toBeInTheDocument();
  });

  it('hides expand/collapse toggle when children is empty', () => {
    render(<TreeNode node={makeNode({ children: [] })} depth={0} isExpanded={false} onToggle={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /expand|collapse/i })).toBeNull();
  });

  it('clicking toggle fires onToggle(id)', async () => {
    const onToggle = vi.fn();
    const node = makeNode({ children: [makeNode({ id: 'c1', title: 'Child' })] });
    render(<TreeNode node={node} depth={0} isExpanded={false} onToggle={onToggle} />);
    await userEvent.click(screen.getByRole('button', { name: /expand|collapse/i }));
    expect(onToggle).toHaveBeenCalledWith('n1');
  });

  it('depth prop controls indentation via CSS variable', () => {
    const { container } = render(
      <TreeNode node={makeNode()} depth={3} isExpanded={false} onToggle={vi.fn()} />,
    );
    const row = container.firstChild as HTMLElement;
    expect(row.style.getPropertyValue('--depth') || row.getAttribute('style')).toMatch(/3/);
  });
});
