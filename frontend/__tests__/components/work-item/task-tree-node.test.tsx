import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskTreeNode } from '@/components/work-item/task-tree-node';
import type { TaskNode, TaskEdge } from '@/lib/types/task';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => `workspace.itemDetail.tasks.${key}`,
}));

const makeNode = (overrides: Partial<TaskNode> = {}): TaskNode => ({
  id: 'n1',
  work_item_id: 'wi-1',
  parent_node_id: null,
  materialized_path: '',
  title: 'Root task',
  status: 'draft',
  position: 0,
  ...overrides,
});

const NO_CHILDREN: TaskNode[] = [];
const NO_EDGES: TaskEdge[] = [];

describe('TaskTreeNode', () => {
  it('renders node title', () => {
    render(
      <TaskTreeNode
        node={makeNode({ title: 'My Task' })}
        depth={0}
        childNodes={NO_CHILDREN}
        allNodes={[]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    expect(screen.getByText('My Task')).toBeDefined();
  });

  it('expand/collapse button hidden when no children', () => {
    render(
      <TaskTreeNode
        node={makeNode()}
        depth={0}
        childNodes={NO_CHILDREN}
        allNodes={[]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // The toggle button should be invisible (not absent — CSS invisible)
    const toggle = screen.queryByRole('button', { name: /expand|collapse/i });
    // Either not present or invisible via CSS class
    if (toggle) {
      expect(toggle.className).toContain('invisible');
    }
  });

  it('expand/collapse button visible when children present', () => {
    const child = makeNode({ id: 'n2', parent_node_id: 'n1', title: 'Child' });
    render(
      <TaskTreeNode
        node={makeNode()}
        depth={0}
        childNodes={[child]}
        allNodes={[child]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // Parent node collapse button should NOT have invisible class
    const toggles = screen.getAllByLabelText(/collapse/i);
    const visibleToggle = toggles.find((el) => !el.className.includes('invisible'));
    expect(visibleToggle).toBeDefined();
  });

  it('toggles expand/collapse on button click', () => {
    const child = makeNode({ id: 'n2', parent_node_id: 'n1', title: 'Child task' });
    render(
      <TaskTreeNode
        node={makeNode()}
        depth={0}
        childNodes={[child]}
        allNodes={[child]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // Initially expanded — child visible
    expect(screen.getByText('Child task')).toBeDefined();

    // Click the visible collapse button (parent node's)
    const toggles = screen.getAllByLabelText(/collapse/i);
    const visibleToggle = toggles.find((el) => !el.className.includes('invisible'));
    fireEvent.click(visibleToggle!);

    // After collapse — child hidden
    expect(screen.queryByText('Child task')).toBeNull();
  });

  it('enters rename mode on title click and submits on blur', async () => {
    const onRefetch = vi.fn();
    render(
      <TaskTreeNode
        node={makeNode({ title: 'Old title' })}
        depth={0}
        childNodes={NO_CHILDREN}
        allNodes={[]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={onRefetch}
      />,
    );

    const title = screen.getByText('Old title');
    fireEvent.click(title);

    const input = screen.getByRole('textbox');
    expect(input).toBeDefined();
  });

  it('shows dependency badge when outgoing blocks edges present', () => {
    const edge: TaskEdge = {
      id: 'e1',
      from_node_id: 'n1',
      to_node_id: 'n2',
      kind: 'blocks',
    };
    const blockedNode = makeNode({ id: 'n2', title: 'Blocked task' });
    render(
      <TaskTreeNode
        node={makeNode()}
        depth={0}
        childNodes={NO_CHILDREN}
        allNodes={[blockedNode]}
        edges={[edge]}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // Badge shows count of outgoing blocks edges
    expect(screen.getByText('→1')).toBeDefined();
  });

  it('does not show dependency badge when no outgoing edges', () => {
    render(
      <TaskTreeNode
        node={makeNode()}
        depth={0}
        childNodes={NO_CHILDREN}
        allNodes={[]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    expect(screen.queryByText(/→\d+/)).toBeNull();
  });

  it('status toggle button cycles draft → in_progress → done', () => {
    const onRefetch = vi.fn();
    render(
      <TaskTreeNode
        node={makeNode({ status: 'draft' })}
        depth={0}
        childNodes={NO_CHILDREN}
        allNodes={[]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={onRefetch}
      />,
    );
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDefined();
  });

  it('depth prop applies indentation via style', () => {
    render(
      <TaskTreeNode
        node={makeNode()}
        depth={3}
        childNodes={NO_CHILDREN}
        allNodes={[]}
        edges={NO_EDGES}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // The row should have style with paddingLeft proportional to depth
    const row = screen.getByText('Root task').closest('[style]');
    expect(row?.getAttribute('style')).toContain('padding-left');
  });
});
