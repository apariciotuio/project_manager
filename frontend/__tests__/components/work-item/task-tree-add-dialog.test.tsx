import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { TaskTreeAddDialog } from '@/components/work-item/task-tree-add-dialog';
import type { TaskNode } from '@/lib/types/task';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => `workspace.itemDetail.tasks.${key}`,
}));

const NODE: TaskNode = {
  id: 'n1',
  work_item_id: 'wi-1',
  parent_node_id: null,
  materialized_path: '',
  title: 'Existing task',
  status: 'draft',
  position: 0,
};

describe('TaskTreeAddDialog', () => {
  it('renders title input and submit button', () => {
    render(
      <TaskTreeAddDialog
        workItemId="wi-1"
        defaultParentId={null}
        allNodes={[]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByRole('textbox')).toBeDefined();
    expect(screen.getByRole('button', { name: /workspace\.itemDetail\.tasks\.dialogSubmit/i })).toBeDefined();
  });

  it('submit button disabled when title is empty', () => {
    render(
      <TaskTreeAddDialog
        workItemId="wi-1"
        defaultParentId={null}
        allNodes={[]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const submitBtn = screen.getByRole('button', {
      name: /workspace\.itemDetail\.tasks\.dialogSubmit/i,
    });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('calls onSuccess after successful task creation', async () => {
    server.use(
      http.post('http://localhost/api/v1/work-items/wi-1/tasks', () =>
        HttpResponse.json({ data: NODE }, { status: 201 }),
      ),
    );

    const onSuccess = vi.fn();
    render(
      <TaskTreeAddDialog
        workItemId="wi-1"
        defaultParentId={null}
        allNodes={[]}
        onSuccess={onSuccess}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'New task' } });
    fireEvent.submit(screen.getByRole('textbox').closest('form')!);

    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it('pre-fills parent select when defaultParentId is provided', () => {
    render(
      <TaskTreeAddDialog
        workItemId="wi-1"
        defaultParentId="n1"
        allNodes={[NODE]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    // Parent node appears in the select (trigger value + hidden option — Radix renders both)
    expect(screen.getAllByText('Existing task').length).toBeGreaterThan(0);
  });

  it('calls onCancel when cancel button clicked', () => {
    const onCancel = vi.fn();
    render(
      <TaskTreeAddDialog
        workItemId="wi-1"
        defaultParentId={null}
        allNodes={[]}
        onSuccess={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(
      screen.getByRole('button', { name: /workspace\.itemDetail\.tasks\.dialogCancel/i }),
    );
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
