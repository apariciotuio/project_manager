/**
 * WCAG contrast parity test.
 * For each theme, asserts every semantic foreground/background pair meets
 * WCAG AA minimum (body text ≥ 4.5:1, UI components ≥ 3:1).
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';
import { hex } from 'wcag-contrast';

const css = readFileSync(join(process.cwd(), 'app/globals.css'), 'utf-8');

function extractBlock(source: string, selector: string): string {
  // Match the selector as a standalone CSS rule (not inside a comment)
  // Use a regex that finds the selector followed by optional whitespace and '{'
  const re = new RegExp(`(?:^|\\n)(${selector.replace('.', '\\.').replace(':', '\\:')})\\s*\\{`, 'g');
  let match: RegExpExecArray | null;
  let selectorIdx = -1;
  while ((match = re.exec(source)) !== null) {
    selectorIdx = match.index + match[0].indexOf(selector);
    break;
  }
  if (selectorIdx === -1) return '';
  let depth = 0;
  let start = -1;
  let end = -1;
  for (let i = selectorIdx; i < source.length; i++) {
    if (source[i] === '{') {
      if (depth === 0) start = i;
      depth++;
    } else if (source[i] === '}') {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  return start !== -1 && end !== -1 ? source.slice(start + 1, end) : '';
}

function parseTokens(block: string): Map<string, string> {
  const map = new Map<string, string>();
  const linePattern = /--([\w-]+)\s*:\s*([^;]+);/g;
  let m: RegExpExecArray | null;
  while ((m = linePattern.exec(block)) !== null) {
    if (m[1] && m[2]) {
      map.set(`--${m[1]}`, m[2].trim());
    }
  }
  return map;
}

/**
 * Convert a CSS HSL token value ("H S% L%" or "H S L") to hex.
 * next-themes stores as "221.2 83.2% 53.3%" or "120 20% 4%"
 */
function hslTokenToHex(value: string): string {
  // Normalise: accept "H S% L%" or "H S L" (with optional %)
  const parts = value.trim().split(/\s+/);
  if (parts.length !== 3) throw new Error(`Cannot parse HSL: "${value}"`);
  const h = parseFloat(parts[0]!);
  const s = parseFloat(parts[1]!) / 100;
  const l = parseFloat(parts[2]!) / 100;

  // HSL → RGB
  const a = s * Math.min(l, 1 - l);
  function f(n: number): number {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color);
  }
  const r = f(0).toString(16).padStart(2, '0');
  const g = f(8).toString(16).padStart(2, '0');
  const b = f(4).toString(16).padStart(2, '0');
  return `#${r}${g}${b}`;
}

const themes = [
  { name: 'light', block: extractBlock(css, ':root') },
  { name: 'dark', block: extractBlock(css, '.dark') },
  { name: 'matrix', block: extractBlock(css, '.matrix') },
];

/**
 * Pairs to check: [foreground token, background token, min ratio, label]
 * AA body = 4.5, AA UI = 3.0
 */
const PAIRS: Array<[string, string, number, string]> = [
  ['--foreground', '--background', 4.5, 'body text'],
  ['--primary-foreground', '--primary', 3.0, 'primary UI'],
  ['--destructive-foreground', '--destructive', 3.0, 'destructive UI'],
  ['--muted-foreground', '--muted', 4.5, 'muted body text'],
  ['--secondary-foreground', '--secondary', 4.5, 'secondary body text'],
  ['--card-foreground', '--card', 4.5, 'card body text'],
  ['--success-foreground', '--success', 3.0, 'success UI'],
  ['--warning-foreground', '--warning', 3.0, 'warning UI'],
  ['--info-foreground', '--info', 3.0, 'info UI'],
];

describe('WCAG contrast parity', () => {
  for (const { name, block } of themes) {
    const tokens = parseTokens(block);

    describe(`theme: ${name}`, () => {
      for (const [fgToken, bgToken, minRatio, label] of PAIRS) {
        it(`${label} (${fgToken} on ${bgToken}) ≥ ${minRatio}:1`, () => {
          const fgValue = tokens.get(fgToken);
          const bgValue = tokens.get(bgToken);
          expect(fgValue, `Missing token ${fgToken} in ${name}`).toBeDefined();
          expect(bgValue, `Missing token ${bgToken} in ${name}`).toBeDefined();

          const fgHex = hslTokenToHex(fgValue!);
          const bgHex = hslTokenToHex(bgValue!);
          const ratio = hex(fgHex, bgHex);

          expect(
            ratio,
            `${name}: ${label} contrast ${ratio.toFixed(2)}:1 < ${minRatio}:1 (${fgToken}=${fgValue} → ${fgHex}, ${bgToken}=${bgValue} → ${bgHex})`
          ).toBeGreaterThanOrEqual(minRatio);
        });
      }
    });
  }
});
