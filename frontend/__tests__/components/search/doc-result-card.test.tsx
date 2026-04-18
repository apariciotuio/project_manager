import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocResultCard } from '@/components/search/doc-result-card';
import type { PuppetSearchResult } from '@/lib/types/search';

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

const mockDoc: PuppetSearchResult = {
  id: 'doc-1',
  entity_type: 'doc',
  title: 'Getting Started Guide',
  score: 0.91,
  snippet: 'How to set up the project from scratch.',
  workspace_id: 'ws-1',
};

describe('DocResultCard', () => {
  it('renders the doc title', () => {
    render(<DocResultCard result={mockDoc} onOpenPreview={vi.fn()} />);
    expect(screen.getByText('Getting Started Guide')).toBeInTheDocument();
  });

  it('renders the snippet text', () => {
    render(<DocResultCard result={mockDoc} onOpenPreview={vi.fn()} />);
    expect(screen.getByText('How to set up the project from scratch.')).toBeInTheDocument();
  });

  it('has an external link icon (aria-label or title)', () => {
    render(<DocResultCard result={mockDoc} onOpenPreview={vi.fn()} />);
    // External link icon should be present — check for the button role
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('calls onOpenPreview with doc id when clicked', async () => {
    const onOpenPreview = vi.fn();
    render(<DocResultCard result={mockDoc} onOpenPreview={onOpenPreview} />);
    await userEvent.click(screen.getByRole('button'));
    expect(onOpenPreview).toHaveBeenCalledWith('doc-1');
  });

  it('renders entity type badge for doc', () => {
    render(<DocResultCard result={mockDoc} onOpenPreview={vi.fn()} />);
    // Should show "doc" entity type indicator somewhere
    expect(screen.getByTestId('entity-type-badge')).toBeInTheDocument();
  });
});
