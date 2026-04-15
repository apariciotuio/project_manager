import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { JiraBadge } from '@/components/domain/jira-badge';
import { LockBadge } from '@/components/domain/lock-badge';
import { VersionChip } from '@/components/domain/version-chip';
import { RollupBadge } from '@/components/domain/rollup-badge';

describe('JiraBadge', () => {
  it('renders with issue key', () => {
    render(<JiraBadge issueKey="PROJ-123" />);
    expect(screen.getByText('PROJ-123')).toBeTruthy();
  });

  it('renders as link when href provided', () => {
    render(<JiraBadge issueKey="PROJ-123" href="https://jira.example.com/PROJ-123" />);
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe('https://jira.example.com/PROJ-123');
  });
});

describe('LockBadge', () => {
  it('renders locked state', () => {
    render(<LockBadge locked />);
    expect(screen.getByRole('img', { hidden: true })).toBeTruthy();
  });

  it('renders unlocked state when not locked', () => {
    const { container } = render(<LockBadge locked={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows who locked it', () => {
    render(<LockBadge locked lockedBy="Ana García" />);
    expect(screen.getByText(/Ana García/)).toBeTruthy();
  });
});

describe('VersionChip', () => {
  it('renders version number', () => {
    render(<VersionChip version="v1.2.3" />);
    expect(screen.getByText('v1.2.3')).toBeTruthy();
  });

  it('renders without v prefix', () => {
    render(<VersionChip version="2.0.0" />);
    expect(screen.getByText('2.0.0')).toBeTruthy();
  });
});

describe('RollupBadge', () => {
  it('renders count', () => {
    render(<RollupBadge total={10} ready={7} />);
    expect(screen.getByText('7/10')).toBeTruthy();
  });

  it('renders accessible label', () => {
    render(<RollupBadge total={5} ready={3} />);
    expect(screen.getByRole('img', { hidden: true }).getAttribute('aria-label')).toContain(
      '3 de 5'
    );
  });
});
