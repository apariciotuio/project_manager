/**
 * Theme token parity test.
 * Parses globals.css and asserts every CSS variable defined in :root
 * also appears in the .dark AND .matrix blocks.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

const css = readFileSync(join(process.cwd(), 'app/globals.css'), 'utf-8');

function extractVariables(block: string): Set<string> {
  const varPattern = /(--[\w-]+)\s*:/g;
  const vars = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = varPattern.exec(block)) !== null) {
    if (m[1]) vars.add(m[1]);
  }
  return vars;
}

function extractBlock(source: string, selector: string): string {
  const selectorIdx = source.indexOf(selector);
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

const rootBlock = extractBlock(css, ':root');
const darkBlock = extractBlock(css, '.dark');
const matrixBlock = extractBlock(css, '.matrix');

const rootVars = extractVariables(rootBlock);
const darkVars = extractVariables(darkBlock);
const matrixVars = extractVariables(matrixBlock);

describe('Theme token parity', () => {
  it('should find :root CSS variables', () => {
    expect(rootVars.size).toBeGreaterThan(0);
  });

  it('should find .dark CSS variables', () => {
    expect(darkVars.size).toBeGreaterThan(0);
  });

  it('should find .matrix CSS variables', () => {
    expect(matrixVars.size).toBeGreaterThan(0);
  });

  it('every :root token must exist in .dark', () => {
    const missing: string[] = [];
    for (const v of rootVars) {
      if (v === '--radius') continue;
      if (!darkVars.has(v)) missing.push(v);
    }
    if (missing.length > 0) {
      throw new Error(
        `Tokens in :root but missing from .dark:\n  ${missing.join('\n  ')}`
      );
    }
  });

  it('every :root token must exist in .matrix', () => {
    const missing: string[] = [];
    for (const v of rootVars) {
      if (v === '--radius') continue;
      if (!matrixVars.has(v)) missing.push(v);
    }
    if (missing.length > 0) {
      throw new Error(
        `Tokens in :root but missing from .matrix:\n  ${missing.join('\n  ')}`
      );
    }
  });

  it('every .dark token must exist in :root', () => {
    const extra: string[] = [];
    for (const v of darkVars) {
      if (!rootVars.has(v)) extra.push(v);
    }
    if (extra.length > 0) {
      throw new Error(
        `Tokens in .dark but missing from :root:\n  ${extra.join('\n  ')}`
      );
    }
  });

  it('every .matrix token must exist in :root', () => {
    const extra: string[] = [];
    for (const v of matrixVars) {
      if (!rootVars.has(v)) extra.push(v);
    }
    if (extra.length > 0) {
      throw new Error(
        `Tokens in .matrix but missing from :root:\n  ${extra.join('\n  ')}`
      );
    }
  });
});
