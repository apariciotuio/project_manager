/**
 * FE-14-04 — ParentPicker component tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { ParentPicker } from '@/components/hierarchy/ParentPicker';

const BASE = 'http://localhost';
const PROJECT_ID = 'proj-1';

function renderPicker(props: Partial<Parameters<typeof ParentPicker>[0]> = {}) {
  return render(
    <ParentPicker
      projectId={PROJECT_ID}
      childType="story"
      value={null}
      onChange={vi.fn()}
      {...props}
    />,
  );
}

describe('ParentPicker', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/work-items`, () =>
        HttpResponse.json({
          data: {
            items: [
              { id: 'e1', title: 'Epic One', type: 'initiative', state: 'draft' },
              { id: 'e2', title: 'Epic Two', type: 'initiative', state: 'ready' },
            ],
            total: 2,
            cursor: null,
            has_next: false,
          },
        }),
      ),
    );
  });

  it('renders nothing (null) when childType = "milestone"', () => {
    const { container } = renderPicker({ childType: 'milestone' });
    expect(container.firstChild).toBeNull();
  });

  it('renders a combobox input for non-milestone types', () => {
    renderPicker({ childType: 'story' });
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('fires API call with type filter restricted to valid parent types for story', async () => {
    let capturedTypes: string[] = [];
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/work-items`, ({ request }) => {
        const url = new URL(request.url);
        capturedTypes = url.searchParams.getAll('type');
        return HttpResponse.json({ data: { items: [], total: 0, cursor: null, has_next: false } });
      }),
    );
    renderPicker({ childType: 'story' });
    const input = screen.getByRole('combobox');
    await userEvent.click(input);
    await userEvent.type(input, 'Epic');
    await waitFor(() => {
      // story valid parents: milestone + initiative (backend HIERARCHY_RULES)
      expect(capturedTypes).toContain('initiative');
      expect(capturedTypes).toContain('milestone');
      expect(capturedTypes).not.toContain('story');
      expect(capturedTypes).not.toContain('task');
    }, { timeout: 1000 });
  });

  it('selecting an item calls onChange with the selected item', async () => {
    const onChange = vi.fn();
    renderPicker({ onChange });
    const input = screen.getByRole('combobox');
    await userEvent.click(input);
    await userEvent.type(input, 'Epic');
    const option = await screen.findByText('Epic One');
    await userEvent.click(option);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'e1' }),
    );
  });

  it('clearing the picker calls onChange(null)', async () => {
    const onChange = vi.fn();
    renderPicker({
      onChange,
      value: { id: 'e1', title: 'Epic One', type: 'initiative' as const, state: 'draft' as const, parent_work_item_id: null, materialized_path: '' },
    });
    const clearBtn = screen.getByRole('button', { name: /clear|remove/i });
    await userEvent.click(clearBtn);
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('pre-populates and displays current parent in edit mode', () => {
    const existing = { id: 'e1', title: 'Existing Epic', type: 'initiative' as const, state: 'draft' as const, parent_work_item_id: null, materialized_path: '' };
    renderPicker({ value: existing });
    expect(screen.getByDisplayValue('Existing Epic')).toBeInTheDocument();
  });

  it('shows "No valid parents found" on empty search results', async () => {
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/work-items`, () =>
        HttpResponse.json({ data: { items: [], total: 0, cursor: null, has_next: false } }),
      ),
    );
    renderPicker();
    const input = screen.getByRole('combobox');
    await userEvent.click(input);
    await userEvent.type(input, 'NonExistent');
    await screen.findByText(/no valid parents/i);
  });

  it('shows inline error message on API error', async () => {
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/work-items`, () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'fail' } }, { status: 500 }),
      ),
    );
    renderPicker();
    const input = screen.getByRole('combobox');
    await userEvent.click(input);
    await userEvent.type(input, 'Epic');
    await screen.findByRole('alert');
  });
});
