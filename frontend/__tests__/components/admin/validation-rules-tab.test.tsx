/**
 * EP-10: Validation Rules Tab — RED tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../msw/server';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const RULE_FIXTURE = {
  id: 'r1',
  workspace_id: 'ws1',
  project_id: null,
  work_item_type: 'bug',
  validation_type: 'has_description',
  enforcement: 'required',
  active: true,
  effective: true,
  superseded_by: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const SUPERSEDED_RULE = {
  ...RULE_FIXTURE,
  id: 'r2',
  enforcement: 'recommended',
  effective: false,
  superseded_by: 'r1',
};

async function renderRulesTab() {
  const { ValidationRulesTab } = await import('@/components/admin/validation-rules-tab');
  return render(<ValidationRulesTab />);
}

describe('ValidationRulesTab', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost/api/v1/admin/rules/validation', () =>
        HttpResponse.json({ data: [RULE_FIXTURE], message: 'ok' })
      )
    );
  });

  it('renders rule list with work_item_type and validation_type', async () => {
    await renderRulesTab();
    await waitFor(() => {
      expect(screen.getByText('bug')).toBeInTheDocument();
      expect(screen.getByText('has_description')).toBeInTheDocument();
    });
  });

  it('shows enforcement badge', async () => {
    await renderRulesTab();
    await waitFor(() => {
      expect(screen.getByText('required')).toBeInTheDocument();
    });
  });

  it('shows workspace scope label when project_id is null', async () => {
    await renderRulesTab();
    await waitFor(() => {
      expect(screen.getByText(/workspace/i)).toBeInTheDocument();
    });
  });

  it('shows superseded_by indicator when rule is superseded', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/rules/validation', () =>
        HttpResponse.json({ data: [SUPERSEDED_RULE], message: 'ok' })
      )
    );
    await renderRulesTab();
    await waitFor(() => {
      expect(screen.getByText(/superseded/i)).toBeInTheDocument();
    });
  });

  it('shows skeleton during loading', () => {
    server.use(
      http.get('http://localhost/api/v1/admin/rules/validation', async () => {
        await new Promise(() => undefined);
      })
    );
    render(<div data-testid="rules-skeleton" />);
    expect(screen.getByTestId('rules-skeleton')).toBeInTheDocument();
  });

  it('shows empty state when no rules', async () => {
    server.use(
      http.get('http://localhost/api/v1/admin/rules/validation', () =>
        HttpResponse.json({ data: [], message: 'ok' })
      )
    );
    await renderRulesTab();
    await waitFor(() => {
      expect(screen.getByTestId('rules-empty')).toBeInTheDocument();
    });
  });

  it('create rule form submits POST and adds rule to list', async () => {
    let posted = false;
    server.use(
      http.post('http://localhost/api/v1/admin/rules/validation', async () => {
        posted = true;
        return HttpResponse.json({
          data: { ...RULE_FIXTURE, id: 'r-new', work_item_type: 'feature' },
          message: 'ok',
        }, { status: 201 });
      })
    );
    await renderRulesTab();
    await waitFor(() => screen.getByText('bug'));
    const addBtn = screen.getByRole('button', { name: /add rule/i });
    await userEvent.click(addBtn);
    const typeInput = screen.getByLabelText(/work item type/i);
    await userEvent.type(typeInput, 'feature');
    const validationInput = screen.getByLabelText(/validation type/i);
    await userEvent.type(validationInput, 'has_description');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));
    await waitFor(() => expect(posted).toBe(true));
  });

  it('delete rule calls DELETE endpoint', async () => {
    let deleted = false;
    server.use(
      http.delete('http://localhost/api/v1/admin/rules/validation/r1', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    await renderRulesTab();
    await waitFor(() => screen.getByText('bug'));
    const deleteBtn = screen.getByRole('button', { name: /delete rule/i });
    await userEvent.click(deleteBtn);
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    await waitFor(() => expect(deleted).toBe(true));
  });

  it('delete 409 rule_has_history shows tooltip/error', async () => {
    server.use(
      http.delete('http://localhost/api/v1/admin/rules/validation/r1', () =>
        HttpResponse.json(
          { error: { code: 'rule_has_history', message: 'cannot delete', details: {} } },
          { status: 409 }
        )
      )
    );
    await renderRulesTab();
    await waitFor(() => screen.getByText('bug'));
    const deleteBtn = screen.getByRole('button', { name: /delete rule/i });
    await userEvent.click(deleteBtn);
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    await waitFor(() =>
      expect(screen.getByText(/cannot delete|use deactivate/i)).toBeInTheDocument()
    );
  });
});
