import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';
import { CompletenessPanel } from '@/components/work-item/completeness-panel';

vi.mock('next-intl', () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const BASE = 'http://localhost';

const COMPLETENESS_RESPONSE = {
  data: {
    score: 65,
    level: 'medium',
    dimensions: [
      { dimension: 'acceptance_criteria', weight: 0.3, applicable: true, filled: false, score: 0.0, message: 'Define at least 2 ACs.' },
      { dimension: 'solution_description', weight: 0.2, applicable: true, filled: true, score: 1.0, message: null },
    ],
    cached: false,
  },
};

const GAPS_RESPONSE = {
  data: [
    { dimension: 'acceptance_criteria', message: 'Define at least 2 ACs.', severity: 'blocking' },
  ],
};

function setupHandlers() {
  server.use(
    http.get(`${BASE}/api/v1/work-items/wi-1/completeness`, () =>
      HttpResponse.json(COMPLETENESS_RESPONSE)
    ),
    http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
      HttpResponse.json(GAPS_RESPONSE)
    )
  );
}

describe('CompletenessPanel', () => {
  it('renders skeleton while loading', () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/completeness`, async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      }),
      http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
        HttpResponse.json({ data: [] })
      )
    );
    render(<CompletenessPanel workItemId="wi-1" />);
    // While loading, no score is visible
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it('renders overall score', async () => {
    setupHandlers();
    render(<CompletenessPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('65')).toBeInTheDocument());
  });

  it('renders level badge', async () => {
    setupHandlers();
    render(<CompletenessPanel workItemId="wi-1" />);

    await waitFor(() =>
      expect(screen.getByTestId('completeness-level-badge')).toBeInTheDocument()
    );
  });

  it('renders one row per applicable dimension', async () => {
    setupHandlers();
    render(<CompletenessPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('65')).toBeInTheDocument());

    // Two applicable dimensions
    const rows = screen.getAllByTestId('dimension-row');
    expect(rows).toHaveLength(2);
  });

  it('overlays gap message on matching dimension row', async () => {
    setupHandlers();
    render(<CompletenessPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('Define at least 2 ACs.')).toBeInTheDocument());
  });

  it('shows cached badge when cached=true', async () => {
    server.use(
      http.get(`${BASE}/api/v1/work-items/wi-1/completeness`, () =>
        HttpResponse.json({ data: { ...COMPLETENESS_RESPONSE.data, cached: true } })
      ),
      http.get(`${BASE}/api/v1/work-items/wi-1/gaps`, () =>
        HttpResponse.json({ data: [] })
      )
    );

    render(<CompletenessPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByTestId('cached-badge')).toBeInTheDocument());
  });

  it('does not show cached badge when cached=false', async () => {
    setupHandlers();
    render(<CompletenessPanel workItemId="wi-1" />);

    await waitFor(() => expect(screen.getByText('65')).toBeInTheDocument());
    expect(screen.queryByTestId('cached-badge')).not.toBeInTheDocument();
  });
});
