import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskTree } from '@/components/work-item/task-tree';
import type { TaskTree as TaskTreeType } from '@/lib/types/task';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => `workspace.itemDetail.tasks.${key}`,
}));

const EMPTY_TREE: TaskTreeType = { nodes: [], edges: [] };

const SINGLE_NODE_TREE: TaskTreeType = {
  nodes: [
    {
      id: 'n1',
      work_item_id: 'wi-1',
      parent_node_id: null,
      materialized_path: '',
      title: 'Root task',
      status: 'draft',
      position: 0,
    },
  ],
  edges: [],
};

const NESTED_TREE: TaskTreeType = {
  nodes: [
    {
      id: 'n1',
      work_item_id: 'wi-1',
      parent_node_id: null,
      materialized_path: '',
      title: 'Level 1',
      status: 'draft',
      position: 0,
    },
    {
      id: 'n2',
      work_item_id: 'wi-1',
      parent_node_id: 'n1',
      materialized_path: 'n1',
      title: 'Level 2',
      status: 'in_progress',
      position: 0,
    },
    {
      id: 'n3',
      work_item_id: 'wi-1',
      parent_node_id: 'n2',
      materialized_path: 'n1.n2',
      title: 'Level 3',
      status: 'done',
      position: 0,
    },
  ],
  edges: [],
};

const SIBLING_TREE: TaskTreeType = {
  nodes: [
    {
      id: 'n1',
      work_item_id: 'wi-1',
      parent_node_id: null,
      materialized_path: '',
      title: 'First',
      status: 'draft',
      position: 0,
    },
    {
      id: 'n2',
      work_item_id: 'wi-1',
      parent_node_id: null,
      materialized_path: '',
      title: 'Second',
      status: 'draft',
      position: 1,
    },
    {
      id: 'n3',
      work_item_id: 'wi-1',
      parent_node_id: null,
      materialized_path: '',
      title: 'Third',
      status: 'draft',
      position: 2,
    },
  ],
  edges: [],
};

describe('TaskTree', () => {
  it('renders empty state with add button when no nodes', () => {
    render(
      <TaskTree
        tree={EMPTY_TREE}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // Translation mock returns the key path
    expect(screen.getByText('workspace.itemDetail.tasks.empty')).toBeDefined();
  });

  it('renders single root node', () => {
    render(
      <TaskTree
        tree={SINGLE_NODE_TREE}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    expect(screen.getByText('Root task')).toBeDefined();
  });

  it('renders 3-level nested tree', () => {
    render(
      <TaskTree
        tree={NESTED_TREE}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    expect(screen.getByText('Level 1')).toBeDefined();
    expect(screen.getByText('Level 2')).toBeDefined();
    expect(screen.getByText('Level 3')).toBeDefined();
  });

  it('orders siblings by position', () => {
    render(
      <TaskTree
        tree={SIBLING_TREE}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    const items = screen.getAllByText(/First|Second|Third/);
    const texts = items.map((el) => el.textContent);
    expect(texts[0]).toBe('First');
    expect(texts[1]).toBe('Second');
    expect(texts[2]).toBe('Third');
  });

  it('shows add root task button', () => {
    render(
      <TaskTree
        tree={EMPTY_TREE}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // aria-label uses the translation key path via mock
    const addButton = screen.getByLabelText('workspace.itemDetail.tasks.addRoot');
    expect(addButton).toBeDefined();
  });

  it('hides children after node collapse', () => {
    render(
      <TaskTree
        tree={NESTED_TREE}
        workItemId="wi-1"
        onRefetch={vi.fn()}
      />,
    );
    // Collapse the root node (Level 1). Multiple collapse buttons — pick the visible one.
    const collapseButtons = screen.getAllByLabelText('workspace.itemDetail.tasks.collapse');
    const rootBtn = collapseButtons.find((el) => !el.className.includes('invisible'));
    fireEvent.click(rootBtn!);

    expect(screen.queryByText('Level 2')).toBeNull();
    expect(screen.queryByText('Level 3')).toBeNull();
  });
});
