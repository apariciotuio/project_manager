/**
 * StickyActionBar tests — EP-12 Group 1
 */
import { render, screen } from '@testing-library/react';
import { StickyActionBar } from '@/components/layout/sticky-action-bar';

describe('StickyActionBar', () => {
  it('renders children', () => {
    render(
      <StickyActionBar>
        <button>Save</button>
      </StickyActionBar>,
    );
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });

  it('has fixed positioning at bottom (mobile)', () => {
    render(
      <StickyActionBar>
        <button>Save</button>
      </StickyActionBar>,
    );
    const bar = screen.getByTestId('sticky-action-bar');
    expect(bar.className).toMatch(/fixed|sticky/);
    expect(bar.className).toMatch(/bottom/);
  });

  it('renders without fixed positioning on desktop via md: class', () => {
    render(
      <StickyActionBar>
        <button>Save</button>
      </StickyActionBar>,
    );
    // The component should have md:relative or md:static class
    const bar = screen.getByTestId('sticky-action-bar');
    expect(bar.className).toMatch(/md:/);
  });

  it('has safe-area inset bottom padding for notched phones', () => {
    render(
      <StickyActionBar>
        <button>Save</button>
      </StickyActionBar>,
    );
    const bar = screen.getByTestId('sticky-action-bar');
    // pb-safe or similar env(safe-area-inset-bottom) support
    expect(bar.className).toMatch(/pb-|safe/);
  });
});
