/**
 * EP-10: Context Presets Tab — RED tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const PRESET_FIXTURE = {
  id: 'cp1',
  workspace_id: 'ws1',
  name: 'Backend Context',
  description: 'Context for backend team',
  sources: [{ type: 'url', label: 'API Docs', url: 'https://docs.example.com' }],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

async function renderPresetsTab() {
  const { ContextPresetsTab } = await import('@/components/admin/context-presets-tab');
  return render(<ContextPresetsTab />);
}

describe('ContextPresetsTab', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/admin/context-presets', () =>
        HttpResponse.json({ data: [PRESET_FIXTURE], message: 'ok' })
      )
    );
  });

  it('renders preset list with name', async () => {
    await renderPresetsTab();
    await waitFor(() => {
      expect(screen.getByText('Backend Context')).toBeInTheDocument();
    });
  });

  it('shows description when present', async () => {
    await renderPresetsTab();
    await waitFor(() => {
      expect(screen.getByText('Context for backend team')).toBeInTheDocument();
    });
  });

  it('shows empty state when no presets', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/context-presets', () =>
        HttpResponse.json({ data: [], message: 'ok' })
      )
    );
    await renderPresetsTab();
    await waitFor(() => {
      expect(screen.getByTestId('presets-empty')).toBeInTheDocument();
    });
  });

  it('create preset form submits POST', async () => {
    let posted = false;
    server.use(
      http.post('http://localhost/api/v1/admin/context-presets', async () => {
        posted = true;
        return HttpResponse.json({
          data: { ...PRESET_FIXTURE, id: 'cp-new', name: 'New Preset' },
          message: 'ok',
        }, { status: 201 });
      })
    );
    await renderPresetsTab();
    await waitFor(() => screen.getByText('Backend Context'));
    await userEvent.click(screen.getByRole('button', { name: /new preset/i }));
    const nameInput = screen.getByLabelText(/name/i);
    await userEvent.type(nameInput, 'New Preset');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));
    await waitFor(() => expect(posted).toBe(true));
  });

  it('delete calls DELETE endpoint', async () => {
    let deleted = false;
    server.use(
      http.delete('http://localhost/api/v1/admin/context-presets/cp1', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    await renderPresetsTab();
    await waitFor(() => screen.getByText('Backend Context'));
    await userEvent.click(screen.getByRole('button', { name: /delete preset/i }));
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    await waitFor(() => expect(deleted).toBe(true));
  });

  it('delete 409 preset_in_use shows error', async () => {
    server.use(
      http.delete('http://localhost/api/v1/admin/context-presets/cp1', () =>
        HttpResponse.json(
          { error: { code: 'preset_in_use', message: 'in use by 2 projects', details: {} } },
          { status: 409 }
        )
      )
    );
    await renderPresetsTab();
    await waitFor(() => screen.getByText('Backend Context'));
    await userEvent.click(screen.getByRole('button', { name: /delete preset/i }));
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    await waitFor(() =>
      expect(screen.getByText(/in use by/i)).toBeInTheDocument()
    );
  });
});
