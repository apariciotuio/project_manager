import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TagChip } from '@/components/domain/tag-chip';
import { TagChipList } from '@/components/domain/tag-chip-list';

describe('TagChip', () => {
  const tag = { id: '1', name: 'frontend', color: '#3b82f6' };

  it('renders tag name', () => {
    render(<TagChip tag={tag} />);
    expect(screen.getByText('frontend')).toBeTruthy();
  });

  it('uses tag color as background with opacity', () => {
    const { container } = render(<TagChip tag={tag} />);
    const chip = container.firstChild as HTMLElement;
    expect(chip?.style.backgroundColor).toBeTruthy();
  });

  it('renders as button when onClick provided', () => {
    render(<TagChip tag={tag} onClick={() => {}} />);
    expect(screen.getByRole('button')).toBeTruthy();
  });

  it('renders as span when no onClick', () => {
    render(<TagChip tag={tag} />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('TagChipList', () => {
  const tags = [
    { id: '1', name: 'frontend', color: '#3b82f6' },
    { id: '2', name: 'backend', color: '#10b981' },
    { id: '3', name: 'design', color: '#f59e0b' },
  ];

  it('renders all tags when under max', () => {
    render(<TagChipList tags={tags} max={5} />);
    expect(screen.getByText('frontend')).toBeTruthy();
    expect(screen.getByText('backend')).toBeTruthy();
    expect(screen.getByText('design')).toBeTruthy();
  });

  it('shows overflow badge when over max', () => {
    render(<TagChipList tags={tags} max={2} />);
    expect(screen.getByText('frontend')).toBeTruthy();
    expect(screen.getByText('backend')).toBeTruthy();
    expect(screen.queryByText('design')).toBeNull();
    expect(screen.getByText('+1')).toBeTruthy();
  });

  it('renders empty without error', () => {
    const { container } = render(<TagChipList tags={[]} max={5} />);
    expect(container.firstChild).toBeTruthy();
  });
});
