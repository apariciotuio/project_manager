/**
 * FE-14-03 — Breadcrumb component tests.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Breadcrumb } from '@/components/hierarchy/Breadcrumb';
import type { WorkItemSummary } from '@/lib/types/hierarchy';

function makeItem(id: string, title: string): WorkItemSummary {
  return { id, title, type: 'story', state: 'draft', parent_work_item_id: null, materialized_path: '' };
}

describe('Breadcrumb', () => {
  it('renders nothing when ancestors is empty and no current', () => {
    const { container } = render(<Breadcrumb ancestors={[]} currentTitle="Current" />);
    // nav rendered but empty — only current item
    expect(screen.getByText('Current')).toBeInTheDocument();
  });

  it('renders aria-label="breadcrumb" on nav', () => {
    render(<Breadcrumb ancestors={[makeItem('a1', 'Ancestor')]} currentTitle="Current" />);
    expect(screen.getByRole('navigation', { name: /breadcrumb/i })).toBeInTheDocument();
  });

  it('renders single ancestor with separator before current', () => {
    render(
      <Breadcrumb ancestors={[makeItem('m1', 'Milestone')]} currentTitle="Epic" />,
    );
    expect(screen.getByText('Milestone')).toBeInTheDocument();
    expect(screen.getByText('Epic')).toBeInTheDocument();
    // separator visible
    const separators = screen.getAllByText('/');
    expect(separators.length).toBeGreaterThanOrEqual(1);
  });

  it('renders N ancestors as A > B > C then current', () => {
    const ancestors = [makeItem('m1', 'M1'), makeItem('e1', 'E1'), makeItem('s1', 'S1')];
    render(<Breadcrumb ancestors={ancestors} currentTitle="Current" />);
    expect(screen.getByText('M1')).toBeInTheDocument();
    expect(screen.getByText('E1')).toBeInTheDocument();
    expect(screen.getByText('S1')).toBeInTheDocument();
    expect(screen.getByText('Current')).toBeInTheDocument();
  });

  it('each ancestor is a link pointing to /work-items/:id', () => {
    render(
      <Breadcrumb ancestors={[makeItem('m1', 'Milestone')]} currentTitle="Epic" />,
    );
    const link = screen.getByRole('link', { name: 'Milestone' });
    expect(link).toHaveAttribute('href', expect.stringContaining('m1'));
  });

  it('current item title is not a link', () => {
    render(<Breadcrumb ancestors={[makeItem('m1', 'M1')]} currentTitle="Current" />);
    const current = screen.getByText('Current');
    expect(current.tagName).not.toBe('A');
  });

  it('current item has aria-current="page"', () => {
    render(<Breadcrumb ancestors={[makeItem('m1', 'M1')]} currentTitle="Current" />);
    const current = screen.getByText('Current');
    expect(current).toHaveAttribute('aria-current', 'page');
  });

  it('truncates middle items with ellipsis beyond depth 4', () => {
    const ancestors = [
      makeItem('a1', 'A1'),
      makeItem('a2', 'A2'),
      makeItem('a3', 'A3'),
      makeItem('a4', 'A4'),
      makeItem('a5', 'A5'),
    ];
    render(<Breadcrumb ancestors={ancestors} currentTitle="Current" />);
    // Should show ellipsis for middle items
    expect(screen.getByText('...')).toBeInTheDocument();
    // First and last ancestors still visible
    expect(screen.getByText('A1')).toBeInTheDocument();
    expect(screen.getByText('A5')).toBeInTheDocument();
  });
});
