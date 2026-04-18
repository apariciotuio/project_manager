import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchResultCard } from '@/components/search/search-result-card';
import type { PuppetSearchResult } from '@/lib/types/search';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockWorkItem: PuppetSearchResult = {
  id: 'wi-1',
  entity_type: 'work_item',
  title: 'Fix the login bug',
  type: 'bug',
  state: 'draft',
  score: 0.95,
  snippet: 'Users cannot log in when using OAuth.',
  workspace_id: 'ws-1',
};

const mockDoc: PuppetSearchResult = {
  id: 'doc-1',
  entity_type: 'doc',
  title: 'API Reference Guide',
  score: 0.88,
  snippet: 'Complete reference for the REST API endpoints.',
  workspace_id: 'ws-1',
};

describe('SearchResultCard', () => {
  it('renders title and snippet for work_item', () => {
    render(<SearchResultCard result={mockWorkItem} slug="acme" onClick={vi.fn()} />);
    expect(screen.getByText('Fix the login bug')).toBeInTheDocument();
    expect(screen.getByText('Users cannot log in when using OAuth.')).toBeInTheDocument();
  });

  it('renders state and type chips for work_item', () => {
    render(<SearchResultCard result={mockWorkItem} slug="acme" onClick={vi.fn()} />);
    expect(screen.getByText('bug')).toBeInTheDocument();
    expect(screen.getByText('draft')).toBeInTheDocument();
  });

  it('links to work item detail for work_item entity type', () => {
    render(<SearchResultCard result={mockWorkItem} slug="acme" onClick={vi.fn()} />);
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/workspace/acme/items/wi-1');
  });

  it('calls onClick when card is clicked', async () => {
    const onClick = vi.fn();
    render(<SearchResultCard result={mockWorkItem} slug="acme" onClick={onClick} />);
    await userEvent.click(screen.getByRole('link'));
    expect(onClick).toHaveBeenCalledWith(mockWorkItem);
  });

  it('renders doc result without state/type chips', () => {
    render(<SearchResultCard result={mockDoc} slug="acme" onClick={vi.fn()} />);
    expect(screen.getByText('API Reference Guide')).toBeInTheDocument();
    expect(screen.queryByText('bug')).not.toBeInTheDocument();
    expect(screen.queryByText('draft')).not.toBeInTheDocument();
  });

  it('sanitizes HTML in snippet — does not execute scripts', () => {
    const malicious: PuppetSearchResult = {
      ...mockWorkItem,
      snippet: '<script>window.__xss = true</script>Plain text',
    };
    render(<SearchResultCard result={malicious} slug="acme" onClick={vi.fn()} />);
    // Script should not be rendered; plain text part should be visible
    expect(screen.getByText('Plain text')).toBeInTheDocument();
    expect((window as unknown as Record<string, unknown>)['__xss']).toBeUndefined();
  });
});
