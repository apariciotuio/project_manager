/**
 * FE-14-02 — RollupBadge component tests.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RollupBadge } from '@/components/hierarchy/RollupBadge';

describe('RollupBadge', () => {
  it('renders nothing when rollup_percent is null', () => {
    const { container } = render(<RollupBadge rollup_percent={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders "0%" with neutral colour class when rollup_percent = 0', () => {
    render(<RollupBadge rollup_percent={0} />);
    const badge = screen.getByRole('img');
    expect(badge).toHaveTextContent('0%');
    expect(badge.className).toMatch(/neutral/);
  });

  it('renders "67%" with in-progress colour class when 0 < rollup_percent < 100', () => {
    render(<RollupBadge rollup_percent={67} />);
    const badge = screen.getByRole('img');
    expect(badge).toHaveTextContent('67%');
    expect(badge.className).toMatch(/in.?progress|progress/i);
  });

  it('renders "100%" with completion colour class when rollup_percent = 100', () => {
    render(<RollupBadge rollup_percent={100} />);
    const badge = screen.getByRole('img');
    expect(badge).toHaveTextContent('100%');
    expect(badge.className).toMatch(/complete|ready/i);
  });

  it('renders stale/recalculating indicator when stale = true', () => {
    render(<RollupBadge rollup_percent={50} stale />);
    expect(screen.getByRole('img')).toBeInTheDocument();
    // stale indicator: aria-label or visible text contains recalculating/stale
    const el = screen.getByRole('img');
    expect(el.getAttribute('aria-label') ?? el.textContent).toMatch(/recalcul|stale/i);
  });

  it('does not render stale indicator when stale = false', () => {
    render(<RollupBadge rollup_percent={50} stale={false} />);
    const el = screen.getByRole('img');
    expect(el.getAttribute('aria-label') ?? el.textContent).not.toMatch(/recalcul|stale/i);
  });

  it('snapshot: 0% neutral', () => {
    const { container } = render(<RollupBadge rollup_percent={0} />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it('snapshot: 50% in-progress', () => {
    const { container } = render(<RollupBadge rollup_percent={50} />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it('snapshot: 100% complete', () => {
    const { container } = render(<RollupBadge rollup_percent={100} />);
    expect(container.firstChild).toMatchSnapshot();
  });
});
