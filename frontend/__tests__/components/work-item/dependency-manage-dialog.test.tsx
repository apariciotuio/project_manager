import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { DependencyManageDialog } from '@/components/work-item/dependency-manage-dialog';
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

const makeEdge = (id: string, fromId: string, toId: string): TaskEdge => ({
  id,
  from_node_id: fromId,
  to_node_id: toId,
  kind: 'blocks',
});

const NODE_A = makeNode('n1', 'Task A');
const NODE_B = makeNode('n2', 'Task B');
const NODE_C = makeNode('n3', 'Task C');

describe('DependencyManageDialog', () => {
  it('renders existing blocks edges for the source node', () => {
    const edge = makeEdge('e1', 'n1', 'n2');
    render(
      <DependencyManageDialog
        sourceNode={NODE_A}
        allNodes={[NODE_A, NODE_B, NODE_C]}
        edges={[edge]}
        workItemId="wi-1"
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText('Task B')).toBeDefined();
  });

  it('calls deleteDependency and onSuccess when remove button clicked', async () => {
    const edge = makeEdge('e1', 'n1', 'n2');
    server.use(
      http.delete('http://localhost/api/v1/tasks/n1/dependencies/e1', () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );

    const onSuccess = vi.fn();
    render(
      <DependencyManageDialog
        sourceNode={NODE_A}
        allNodes={[NODE_A, NODE_B, NODE_C]}
        edges={[edge]}
        workItemId="wi-1"
        onSuccess={onSuccess}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: /workspace\.itemDetail\.tasks\.dependencyRemove/i,
      }),
    );

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it('calls createDependency and onSuccess when a target is selected and submitted', async () => {
    const newEdge = makeEdge('e2', 'n1', 'n3');
    server.use(
      http.post('http://localhost/api/v1/tasks/n1/dependencies', () =>
        HttpResponse.json({ data: newEdge }, { status: 201 }),
      ),
    );

    const onSuccess = vi.fn();
    render(
      <DependencyManageDialog
        sourceNode={NODE_A}
        allNodes={[NODE_A, NODE_B, NODE_C]}
        edges={[]}
        workItemId="wi-1"
        onSuccess={onSuccess}
        onCancel={vi.fn()}
      />,
    );

    // Select a target node — the select should list sibling nodes (not the source)
    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'n3' } });

    fireEvent.click(
      screen.getByRole('button', {
        name: /workspace\.itemDetail\.tasks\.dependencyAdd/i,
      }),
    );

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it('calls onCancel when cancel/close button clicked', () => {
    const onCancel = vi.fn();
    render(
      <DependencyManageDialog
        sourceNode={NODE_A}
        allNodes={[NODE_A, NODE_B]}
        edges={[]}
        workItemId="wi-1"
        onSuccess={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: /workspace\.itemDetail\.tasks\.dialogCancel/i,
      }),
    );
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
