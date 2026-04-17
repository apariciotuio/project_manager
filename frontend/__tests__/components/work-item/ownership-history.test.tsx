import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { OwnershipHistory } from '@/components/work-item/ownership-history';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    const base = `${ns}.${key}`;
    if (params && typeof params === 'object') {
      const entries = Object.entries(params).map(([k, v]) => `${k}=${v}`).join(',');
      return `${base}(${entries})`;
    }
    return base;
  },
}));

describe('OwnershipHistory', () => {
  it('shows empty-state when there are no changes', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ownership-history', () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    render(<OwnershipHistory workItemId="wi-1" />);
    await waitFor(() =>
      expect(
        screen.getByText(/workspace\.itemDetail\.audit\.ownership\.empty/i),
      ).toBeInTheDocument(),
    );
  });

  it('lists ownership changes with previous → new and reason', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ownership-history', () =>
        HttpResponse.json({
          data: [
            {
              id: 'o1',
              work_item_id: 'wi-1',
              previous_owner_id: 'user-1',
              new_owner_id: 'user-2',
              changed_by: 'user-1',
              changed_at: '2026-02-02T10:00:00Z',
              reason: 'On leave',
            },
          ],
        }),
      ),
    );
    render(<OwnershipHistory workItemId="wi-1" />);
    await waitFor(() => expect(screen.getByText(/user-1 → user-2/)).toBeInTheDocument());
    expect(screen.getByText(/On leave/)).toBeInTheDocument();
  });

  it('surfaces error on failure', async () => {
    server.use(
      http.get('http://localhost/api/v1/work-items/wi-1/ownership-history', () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL_ERROR', message: 'boom' } },
          { status: 500 },
        ),
      ),
    );
    render(<OwnershipHistory workItemId="wi-1" />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });
});
