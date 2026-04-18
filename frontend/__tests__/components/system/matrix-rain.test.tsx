import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

let mockTheme: string = 'matrix';
let mockReducedMotion = false;
let mockRainEnabled = false;

vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: mockTheme }),
}));

vi.mock('@/lib/theme/trinity', () => ({
  isRainEnabled: () => mockRainEnabled,
  getPreviousTheme: () => 'dark',
  setPreviousTheme: vi.fn(),
  setRainEnabled: vi.fn(),
}));

import { MatrixRain } from '@/components/system/matrix-rain';

// Tracks listeners registered via matchMedia.addEventListener so tests can fire them
type MQListener = (e: MediaQueryListEvent) => void;
let motionListeners: MQListener[] = [];

function buildMatchMedia(reducedMotion: boolean) {
  return (query: string) => ({
    matches: query.includes('reduce') ? reducedMotion : false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: (_: string, fn: MQListener) => { motionListeners.push(fn); },
    removeEventListener: (_: string, fn: MQListener) => {
      motionListeners = motionListeners.filter((l) => l !== fn);
    },
    dispatchEvent: () => false,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'matrix';
  mockReducedMotion = false;
  mockRainEnabled = true;
  motionListeners = [];

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: buildMatchMedia(false),
  });
});

describe('MatrixRain', () => {
  it('does not render when theme is not "matrix"', () => {
    mockTheme = 'light';
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeNull();
  });

  it('does not render when isRainEnabled() is false', () => {
    mockTheme = 'matrix';
    mockRainEnabled = false;
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeNull();
  });

  it('does not render when prefers-reduced-motion is reduce on initial mount', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: buildMatchMedia(true),
    });
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeNull();
  });

  it('renders a canvas when all conditions are met', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    mockReducedMotion = false;
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeTruthy();
  });

  it('canvas has aria-hidden="true"', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    const { container } = render(<MatrixRain />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.getAttribute('aria-hidden')).toBe('true');
  });

  it('canvas has pointer-events-none class', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    const { container } = render(<MatrixRain />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.className).toMatch(/pointer-events-none/);
  });

  // SF-2: reduced-motion reactivity
  it('hides canvas when reduced-motion preference changes to true after render', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeTruthy();

    act(() => {
      // Simulate the OS flipping reduced-motion on
      motionListeners.forEach((fn) =>
        fn({ matches: true, media: '(prefers-reduced-motion: reduce)' } as MediaQueryListEvent),
      );
    });

    expect(container.querySelector('canvas')).toBeNull();
  });

  it('shows canvas again when reduced-motion preference changes back to false', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: buildMatchMedia(true),
    });
    mockTheme = 'matrix';
    mockRainEnabled = true;
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeNull();

    act(() => {
      motionListeners.forEach((fn) =>
        fn({ matches: false, media: '(prefers-reduced-motion: reduce)' } as MediaQueryListEvent),
      );
    });

    expect(container.querySelector('canvas')).toBeTruthy();
  });

  // SF-3: storage event reactivity
  it('shows canvas when storage event enables rain', () => {
    mockTheme = 'matrix';
    mockRainEnabled = false; // initially disabled
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeNull();

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'trinity:rainEnabled', newValue: 'true' }),
      );
    });

    expect(container.querySelector('canvas')).toBeTruthy();
  });

  it('hides canvas when storage event disables rain', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeTruthy();

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'trinity:rainEnabled', newValue: 'false' }),
      );
    });

    expect(container.querySelector('canvas')).toBeNull();
  });

  it('ignores storage events for unrelated keys', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    const { container } = render(<MatrixRain />);
    expect(container.querySelector('canvas')).toBeTruthy();

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'other:key', newValue: 'false' }),
      );
    });

    // Should still render
    expect(container.querySelector('canvas')).toBeTruthy();
  });
});
