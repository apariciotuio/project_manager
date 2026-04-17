import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DependencyBadge } from '@/components/work-item/dependency-badge';
import type { TaskEdge, TaskNode } from '@/lib/types/task';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => `workspace.itemDetail.tasks.${key}`,
}));

const makeNode = (id: string, title: string): TaskNode => ({
  id,
  work_item_id: 'wi-1',
  parent_node_id: null,
  materialized_path: '',
  title,
  status: 'draft',
  position: 0,
});

const makeEdge = (fromId: string, toId: string): TaskEdge => ({
  id: `e-${fromId}-${toId}`,
  from_node_id: fromId,
  to_node_id: toId,
  kind: 'blocks',
});

describe('DependencyBadge', () => {
  it('renders nothing when there are no outgoing blocks edges', () => {
    const { container } = render(
      <DependencyBadge
        nodeId="n1"
        edges={[]}
        allNodes={[]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when edges are for other nodes', () => {
    const { container } = render(
      <DependencyBadge
        nodeId="n1"
        edges={[makeEdge('n2', 'n3')]}
        allNodes={[makeNode('n2', 'Other'), makeNode('n3', 'Third')]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders count badge when outgoing blocks edges present', () => {
    render(
      <DependencyBadge
        nodeId="n1"
        edges={[makeEdge('n1', 'n2'), makeEdge('n1', 'n3')]}
        allNodes={[makeNode('n2', 'Task B'), makeNode('n3', 'Task C')]}
      />,
    );
    expect(screen.getByText('→2')).toBeDefined();
  });

  it('tooltip contains blocked task titles', () => {
    render(
      <DependencyBadge
        nodeId="n1"
        edges={[makeEdge('n1', 'n2')]}
        allNodes={[makeNode('n2', 'Blocked task')]}
      />,
    );
    const badge = screen.getByText('→1');
    const title = badge.getAttribute('title') ?? badge.closest('[title]')?.getAttribute('title');
    expect(title).toContain('Blocked task');
  });

  it('does not render relates_to edges in count', () => {
    const relatesEdge: TaskEdge = {
      id: 'e-rel',
      from_node_id: 'n1',
      to_node_id: 'n2',
      kind: 'relates_to',
    };
    const { container } = render(
      <DependencyBadge
        nodeId="n1"
        edges={[relatesEdge]}
        allNodes={[makeNode('n2', 'Related')]}
      />,
    );
    // relates_to edges should not appear in the blocks badge
    expect(container.firstChild).toBeNull();
  });
});
