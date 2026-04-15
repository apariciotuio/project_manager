import { describe, it, expect } from 'vitest';
import { hexToRgb, relativeLuminance, contrastRatio, pickContrastColor } from '@/lib/color';

describe('hexToRgb', () => {
  it('parses 6-digit hex', () => {
    expect(hexToRgb('#ffffff')).toEqual({ r: 255, g: 255, b: 255 });
    expect(hexToRgb('#000000')).toEqual({ r: 0, g: 0, b: 0 });
    expect(hexToRgb('#ff5733')).toEqual({ r: 255, g: 87, b: 51 });
  });

  it('parses 3-digit hex', () => {
    expect(hexToRgb('#fff')).toEqual({ r: 255, g: 255, b: 255 });
    expect(hexToRgb('#000')).toEqual({ r: 0, g: 0, b: 0 });
  });

  it('returns null for invalid', () => {
    expect(hexToRgb('not-a-color')).toBeNull();
  });
});

describe('relativeLuminance', () => {
  it('white has luminance 1', () => {
    expect(relativeLuminance({ r: 255, g: 255, b: 255 })).toBeCloseTo(1, 3);
  });

  it('black has luminance 0', () => {
    expect(relativeLuminance({ r: 0, g: 0, b: 0 })).toBeCloseTo(0, 5);
  });
});

describe('contrastRatio', () => {
  it('black on white has contrast 21:1', () => {
    const white = { r: 255, g: 255, b: 255 };
    const black = { r: 0, g: 0, b: 0 };
    expect(contrastRatio(white, black)).toBeCloseTo(21, 0);
  });
});

describe('pickContrastColor', () => {
  it('dark background → white text', () => {
    expect(pickContrastColor('#1a1a2e')).toBe('#ffffff');
  });

  it('light background → black text', () => {
    expect(pickContrastColor('#f8f8f8')).toBe('#000000');
  });

  it('dark red background → black text (luminance ~0.2)', () => {
    // #e53e3e has L≈0.20; black contrast is higher
    expect(pickContrastColor('#e53e3e')).toBe('#000000');
  });

  it('very dark red background → white text', () => {
    // #8b0000 (dark red) has much lower luminance → white wins
    expect(pickContrastColor('#8b0000')).toBe('#ffffff');
  });

  it('yellow background → black text', () => {
    expect(pickContrastColor('#ffd700')).toBe('#000000');
  });

  it('returns black for invalid color', () => {
    expect(pickContrastColor('invalid')).toBe('#000000');
  });
});
