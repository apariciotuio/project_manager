declare module 'wcag-contrast' {
  export function luminance(rgb: [number, number, number]): number;
  export function rgb(rgb1: [number, number, number], rgb2: [number, number, number]): number;
  export function hex(color1: string, color2: string): number;
  export function score(ratio: number): 'AAA' | 'AA' | 'AA Large' | 'DNP';
}
