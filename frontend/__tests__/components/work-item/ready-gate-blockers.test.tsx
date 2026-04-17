import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '@/__tests__/msw/server';
import { ReadyGateBlockers } from '@/components/work-item/ready-gate-blockers';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${ns}.${key}(${JSON.stringify(params)})`;
    return `${ns}.${key}`;
  },
}));

const BASE = 'http://localhost';

describe('ReadyGateBlockers', () => {
  it('renders nothing when gate is ok (no blockers)', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/ready-gate`, () =>
        HttpResponse.json({ data: { ok: true, blockers: [] } }),
      ),
    );
    const { container } = render(<ReadyGateBlockers workItemId="wi-1" />);
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it('renders a bullet list of blockers when gate is blocked', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/ready-gate`, () =>
        HttpResponse.json({
          data: {
            ok: false,
            blockers: [
              { code: 'VALIDATION_REQUIRED', rule_id: 'r1', label: 'Has AC', status: 'pending' },
              { code: 'VALIDATION_REQUIRED', rule_id: 'r2', label: 'Has description', status: 'pending' },
            ],
          },
        }),
      ),
    );
    render(<ReadyGateBlockers workItemId="wi-1" />);
    await waitFor(() =>
      expect(screen.getByTestId('ready-gate-blockers')).toBeInTheDocument(),
    );
    expect(screen.getAllByTestId(/^blocker-item-/)).toHaveLength(2);
  });

  it('renders blocker labels as list items', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/ready-gate`, () =>
        HttpResponse.json({
          data: {
            ok: false,
            blockers: [
              { code: 'VALIDATION_REQUIRED', rule_id: 'r1', label: 'Has AC', status: 'pending' },
            ],
          },
        }),
      ),
    );
    render(<ReadyGateBlockers workItemId="wi-1" />);
    await waitFor(() => screen.getByText('Has AC'));
    expect(screen.getByTestId('blocker-item-r1')).toHaveTextContent('Has AC');
  });
});
