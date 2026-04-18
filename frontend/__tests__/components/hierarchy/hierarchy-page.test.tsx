/**
 * FE-14-09 — Hierarchy page integration tests.
 * Tests the HierarchyPage component (used by the route page.tsx).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { HierarchyPageView } from '@/components/hierarchy/HierarchyPageView';

const BASE = 'http://localhost';
const PROJECT_ID = 'proj-1';

const hierarchyResponse = {
  data: {
    roots: [
      { id: 'm1', title: 'Milestone Alpha', type: 'milestone', state: 'draft', parent_work_item_id: null, materialized_path: '', children: [] },
    ],
    unparented: [],
    meta: { truncated: false, next_cursor: null },
  },
};

describe('HierarchyPageView', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/hierarchy`, () =>
        HttpResponse.json(hierarchyResponse),
      ),
    );
  });

  it('fetches getProjectHierarchy on mount', async () => {
    let called = false;
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/hierarchy`, () => {
        called = true;
        return HttpResponse.json(hierarchyResponse);
      }),
    );
    render(<HierarchyPageView projectId={PROJECT_ID} projectName="Project Alpha" />);
    await waitFor(() => expect(called).toBe(true));
  });

  it('shows loading state while fetching', () => {
    // Don't resolve the request — loading state persists
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/hierarchy`, async () => {
        await new Promise(() => {/* never resolves */});
        return HttpResponse.json(hierarchyResponse);
      }),
    );
    render(<HierarchyPageView projectId={PROJECT_ID} projectName="Project Alpha" />);
    expect(screen.getByTestId('tree-loading-skeleton')).toBeInTheDocument();
  });

  it('shows error state with retry button on fetch failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/projects/${PROJECT_ID}/hierarchy`, () =>
        HttpResponse.json({ error: { code: 'SERVER_ERROR', message: 'fail' } }, { status: 500 }),
      ),
    );
    render(<HierarchyPageView projectId={PROJECT_ID} projectName="Project Alpha" />);
    await screen.findByRole('button', { name: /retry/i });
  });

  it('renders TreeView with fetched data', async () => {
    render(<HierarchyPageView projectId={PROJECT_ID} projectName="Project Alpha" />);
    await screen.findByText('Milestone Alpha');
  });

  it('renders page title with project name', async () => {
    render(<HierarchyPageView projectId={PROJECT_ID} projectName="Project Alpha" />);
    // Wait for data to show the title is rendered
    expect(screen.getByRole('heading', { name: /Project Alpha/i })).toBeInTheDocument();
  });
});
