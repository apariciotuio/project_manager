/**
 * Color utility functions for luminance-based contrast computation.
 * Used by TagChip to compute accessible text color on arbitrary background.
 */

export interface RGB {
  r: number;
  g: number;
  b: number;
}

/** Parse hex color (#rgb or #rrggbb) to RGB. Returns null for invalid input. */
export function hexToRgb(hex: string): RGB | null {
  const cleaned = hex.replace('#', '');
  let full: string;

  if (cleaned.length === 3) {
    full = cleaned
      .split('')
      .map((c) => c + c)
      .join('');
  } else if (cleaned.length === 6) {
    full = cleaned;
  } else {
    return null;
  }

  const num = parseInt(full, 16);
  if (isNaN(num)) return null;

  return {
    r: (num >> 16) & 0xff,
    g: (num >> 8) & 0xff,
    b: num & 0xff,
  };
}

/**
 * Relative luminance per WCAG 2.1.
 * https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
 */
export function relativeLuminance(rgb: RGB): number {
  function linearize(v: number): number {
    const sRGB = v / 255;
    return sRGB <= 0.03928 ? sRGB / 12.92 : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  }
  const R = linearize(rgb.r);
  const G = linearize(rgb.g);
  const B = linearize(rgb.b);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

/** WCAG contrast ratio between two RGB values. */
export function contrastRatio(a: RGB, b: RGB): number {
  const L1 = relativeLuminance(a);
  const L2 = relativeLuminance(b);
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Given a background hex color, return '#ffffff' or '#000000'
 * whichever has better contrast per WCAG.
 * Cached with a Map for performance in lists.
 */
const cache = new Map<string, '#ffffff' | '#000000'>();

export function pickContrastColor(hex: string): '#ffffff' | '#000000' {
  const cached = cache.get(hex);
  if (cached) return cached;

  const rgb = hexToRgb(hex);
  if (!rgb) return '#000000';

  const white: RGB = { r: 255, g: 255, b: 255 };
  const black: RGB = { r: 0, g: 0, b: 0 };

  const contrastWhite = contrastRatio(rgb, white);
  const contrastBlack = contrastRatio(rgb, black);

  const result = contrastWhite >= contrastBlack ? '#ffffff' : '#000000';
  cache.set(hex, result);
  return result;
}
