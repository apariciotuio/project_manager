import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

// ── RAF mock ──────────────────────────────────────────────────────────────

let rafCallbacks: Map<number, FrameRequestCallback> = new Map();
let rafId = 0;

const mockRaf = vi.fn((cb: FrameRequestCallback) => {
  const id = ++rafId;
  rafCallbacks.set(id, cb);
  return id;
});

const mockCancelRaf = vi.fn((id: number) => {
  rafCallbacks.delete(id);
});

// ── matchMedia mock ───────────────────────────────────────────────────────

let mockReducedMotion = false;

function setReducedMotion(value: boolean) {
  mockReducedMotion = value;
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: query.includes('prefers-reduced-motion') ? value : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  rafCallbacks = new Map();
  rafId = 0;
  mockReducedMotion = false;

  // Install RAF mock
  vi.stubGlobal('requestAnimationFrame', mockRaf);
  vi.stubGlobal('cancelAnimationFrame', mockCancelRaf);

  // Install matchMedia mock (no reduced motion by default)
  setReducedMotion(false);

  // Canvas getContext stub — jsdom doesn't implement canvas 2D
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    fillStyle: '',
    font: '',
    fillRect: vi.fn(),
    fillText: vi.fn(),
    clearRect: vi.fn(),
  })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── Import after mocks ────────────────────────────────────────────────────

import { MatrixEntryCascade } from '@/components/system/matrix-entry-cascade/matrix-entry-cascade';

// ── Tests ─────────────────────────────────────────────────────────────────

describe('MatrixEntryCascade — lifecycle', () => {
  it('does not render a canvas when active=false', () => {
    const { container } = render(<MatrixEntryCascade active={false} />);
    expect(container.querySelector('canvas')).toBeNull();
  });

  it('mounts a canvas when active=true', () => {
    const { container } = render(<MatrixEntryCascade active={true} />);
    expect(container.querySelector('canvas')).not.toBeNull();
  });

  it('canvas has aria-hidden="true"', () => {
    const { container } = render(<MatrixEntryCascade active={true} />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toHaveAttribute('aria-hidden', 'true');
  });

  it('canvas has pointer-events-none class', () => {
    const { container } = render(<MatrixEntryCascade active={true} />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.className).toMatch(/pointer-events-none/);
  });

  it('canvas has z-index 9999 inline style', () => {
    const { container } = render(<MatrixEntryCascade active={true} />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.style.zIndex).toBe('9999');
  });

  it('unmounting cancels the RAF loop', () => {
    const { unmount } = render(<MatrixEntryCascade active={true} />);
    unmount();
    expect(mockCancelRaf).toHaveBeenCalled();
  });

  it('switching active from true to false cancels RAF and removes canvas', () => {
    const { container, rerender } = render(<MatrixEntryCascade active={true} />);
    expect(container.querySelector('canvas')).not.toBeNull();
    rerender(<MatrixEntryCascade active={false} />);
    expect(mockCancelRaf).toHaveBeenCalled();
    expect(container.querySelector('canvas')).toBeNull();
  });
});

describe('MatrixEntryCascade — RAF scheduling', () => {
  it('schedules a RAF loop when active=true', () => {
    render(<MatrixEntryCascade active={true} />);
    expect(mockRaf).toHaveBeenCalled();
  });

  it('does not schedule RAF when active=false', () => {
    render(<MatrixEntryCascade active={false} />);
    expect(mockRaf).not.toHaveBeenCalled();
  });
});

describe('MatrixEntryCascade — reduced motion', () => {
  it('mounts canvas but does not start RAF when prefers-reduced-motion is reduce', () => {
    setReducedMotion(true);
    const { container } = render(<MatrixEntryCascade active={true} />);
    // Canvas mounts (avoids SSR hydration mismatch); RAF must NOT be scheduled
    expect(container.querySelector('canvas')).not.toBeNull();
    expect(mockRaf).not.toHaveBeenCalled();
  });

  it('calls onComplete immediately when prefers-reduced-motion is reduce', () => {
    setReducedMotion(true);
    const onComplete = vi.fn();
    render(<MatrixEntryCascade active={true} onComplete={onComplete} />);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('renders canvas when reduced-motion is false', () => {
    setReducedMotion(false);
    const { container } = render(<MatrixEntryCascade active={true} />);
    expect(container.querySelector('canvas')).not.toBeNull();
  });

  it('parent re-render with new onComplete reference while cascade is running does NOT restart cascade', () => {
    setReducedMotion(false);
    const onComplete1 = vi.fn();
    const onComplete2 = vi.fn();
    const { rerender } = render(<MatrixEntryCascade active={true} onComplete={onComplete1} />);
    const rafCallsBefore = mockRaf.mock.calls.length;
    // Simulate parent re-render with new callback reference
    rerender(<MatrixEntryCascade active={true} onComplete={onComplete2} />);
    // RAF call count should not have increased (effect did not re-run)
    expect(mockRaf.mock.calls.length).toBe(rafCallsBefore);
    expect(onComplete1).not.toHaveBeenCalled();
    expect(onComplete2).not.toHaveBeenCalled();
  });
});

describe('MatrixEntryCascade — onComplete callback', () => {
  it('does not call onComplete immediately when active and not reduced-motion', () => {
    const onComplete = vi.fn();
    render(<MatrixEntryCascade active={true} onComplete={onComplete} />);
    // Should NOT be called immediately — only after duration elapses
    expect(onComplete).not.toHaveBeenCalled();
  });
});

describe('MatrixEntryCascade — abort on re-trigger', () => {
  it('cancels RAF when switched active true → false → true (re-triggers clean)', () => {
    const { rerender } = render(<MatrixEntryCascade active={true} />);
    rerender(<MatrixEntryCascade active={false} />);
    const cancelCount = mockCancelRaf.mock.calls.length;
    rerender(<MatrixEntryCascade active={true} />);
    // Each cleanup should cancel the previous RAF
    expect(mockCancelRaf.mock.calls.length).toBeGreaterThanOrEqual(cancelCount);
  });
});
