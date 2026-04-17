/**
 * EP-07 FE — VersionHistoryPanel + DiffViewer components.
 *
 * Tests:
 * - renders list of versions
 * - each row has "View diff vs previous" button
 * - clicking opens diff dialog
 * - diff dialog renders changed sections
 * - "Load more" shown when hasMore
 * - error state shown on list failure
 * - diff empty state
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const BASE = 'http://localhost';

const mockVersions = [
  {
    id: 'ver-2',
    work_item_id: 'wi-1',
    version_number: 2,
    trigger: 'content_edit',
    actor_type: 'human',
    actor_id: 'user-1',
    commit_message: 'Updated summary',
    archived: false,
    created_at: '2026-04-17T11:00:00Z',
  },
  {
    id: 'ver-1',
    work_item_id: 'wi-1',
    version_number: 1,
    trigger: 'content_edit',
    actor_type: 'human',
    actor_id: 'user-1',
    commit_message: 'Initial spec',
    archived: false,
    created_at: '2026-04-17T10:00:00Z',
  },
];

const mockDiff = {
  from_version: 1,
  to_version: 2,
  sections_added: [],
  sections_removed: [],
  sections_changed: [
    {
      section_type: 'summary',
      from: 'Old summary',
      to: 'New summary',
      diff_lines: ['-Old summary', '+New summary'],
    },
  ],
  work_item_changed: false,
  task_nodes_changed: false,
};

describe('VersionHistoryPanel', () => {
  it('renders loaded versions', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions`, () =>
        HttpResponse.json({
          data: mockVersions,
          meta: { has_more: false, next_cursor: null },
        }),
      ),
    );

    const { VersionHistoryPanel } = await import(
      '@/components/work-item/version-history-panel'
    );
    render(<VersionHistoryPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('Updated summary')).toBeInTheDocument());
    expect(screen.getByText('Initial spec')).toBeInTheDocument();
  });

  it('shows Load more when hasMore is true', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions`, () =>
        HttpResponse.json({
          data: mockVersions,
          meta: { has_more: true, next_cursor: '1' },
        }),
      ),
    );

    const { VersionHistoryPanel } = await import(
      '@/components/work-item/version-history-panel'
    );
    render(<VersionHistoryPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByRole('button', { name: /loadMore/i })).toBeInTheDocument());
  });

  it('shows error state on failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-fail/versions`, () =>
        HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'not found' } }, { status: 404 }),
      ),
    );

    const { VersionHistoryPanel } = await import(
      '@/components/work-item/version-history-panel'
    );
    render(<VersionHistoryPanel workItemId="wi-fail" />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });

  it('opens diff dialog when View diff clicked', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/versions`, () =>
        HttpResponse.json({
          data: mockVersions,
          meta: { has_more: false, next_cursor: null },
        }),
      ),
      http.get(`${BASE}/api/v1/work-items/wi-1/versions/2/diff`, () =>
        HttpResponse.json({ data: mockDiff }),
      ),
    );

    const { VersionHistoryPanel } = await import(
      '@/components/work-item/version-history-panel'
    );
    render(<VersionHistoryPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('Updated summary')).toBeInTheDocument());

    const diffButtons = screen.getAllByRole('button', { name: /viewDiff|diff/i });
    fireEvent.click(diffButtons[0]!);

    await waitFor(() => expect(screen.getByText(/New summary/)).toBeInTheDocument());
  });
});
