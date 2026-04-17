import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

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

beforeEach(() => {
  vi.clearAllMocks();
  mockTheme = 'matrix';
  mockReducedMotion = false;
  mockRainEnabled = true;

  // Reset matchMedia mock
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: mockReducedMotion,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
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

  it('does not render when prefers-reduced-motion is reduce', () => {
    mockTheme = 'matrix';
    mockRainEnabled = true;
    mockReducedMotion = true;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: query.includes('reduce'),
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
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
});
