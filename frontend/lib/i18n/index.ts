/**
 * EP-19 i18n infrastructure.
 *
 * Pattern: typed dictionary object + thin `t()` getter.
 * This lives alongside next-intl; existing pages that use `useTranslations()`
 * keep working. New domain components import from here.
 *
 * icuLite: handles {variable}, plural/one/other, select patterns.
 */
import { common } from './es/common';
import { errors } from './es/errors';
import { workitem } from './es/workitem';
import { review } from './es/review';
import { hierarchy } from './es/hierarchy';
import { tags } from './es/tags';
import { attachment } from './es/attachment';
import { lock } from './es/lock';
import { mcp } from './es/mcp';
import { assistant } from './es/assistant';
import { role } from './es/role';

export const es = {
  common,
  errors,
  workitem,
  review,
  hierarchy,
  tags,
  attachment,
  lock,
  mcp,
  assistant,
  role,
} as const;

export type Locale = 'es' | 'en';
export type Dict = typeof es;

// -------------------------------------------------------
// icuLite — minimal ICU-compatible interpolation
// Handles: {variable}, {count, plural, one{...} other{...}}, {val, select, a{...} b{...}}
// -------------------------------------------------------

type IcuVars = Record<string, string | number>;

function resolvePluralOrSelect(
  type: 'plural' | 'select',
  key: string,
  value: string | number,
  cases: Record<string, string>,
  vars: IcuVars
): string {
  const strValue = String(value);
  if (type === 'plural') {
    const count = Number(value);
    const form = count === 1 ? 'one' : 'other';
    const tmpl = cases[String(count)] ?? cases[form] ?? cases['other'] ?? '';
    return icuLite(tmpl, { ...vars, [key]: value });
  }
  // select: match value exactly, fall back to 'other'
  const tmpl = cases[strValue] ?? cases['other'] ?? strValue;
  return icuLite(tmpl, { ...vars, [key]: value });
}

function parseCases(casesStr: string): Record<string, string> {
  const result: Record<string, string> = {};
  let i = 0;

  while (i < casesStr.length) {
    // Skip whitespace
    while (i < casesStr.length && /\s/.test(casesStr[i] as string)) i++;
    if (i >= casesStr.length) break;

    // Read the case key (word chars)
    let key = '';
    while (i < casesStr.length && /\w/.test(casesStr[i] as string)) {
      key += casesStr[i++];
    }
    if (!key) { i++; continue; }

    // Skip whitespace
    while (i < casesStr.length && /\s/.test(casesStr[i] as string)) i++;
    if (casesStr[i] !== '{') continue;

    // Depth-aware extraction of the body
    let depth = 0;
    let start = i;
    while (i < casesStr.length) {
      if (casesStr[i] === '{') depth++;
      else if (casesStr[i] === '}') {
        depth--;
        if (depth === 0) { i++; break; }
      }
      i++;
    }
    // body is between start+1 and i-2 (excluding outer braces)
    result[key] = casesStr.slice(start + 1, i - 1);
  }

  return result;
}

export function icuLite(template: string, vars: IcuVars = {}): string {
  let result = '';
  let i = 0;

  while (i < template.length) {
    if (template[i] !== '{') {
      result += template[i++];
      continue;
    }

    // Find the matching closing brace — depth-aware
    let depth = 0;
    let j = i;
    while (j < template.length) {
      if (template[j] === '{') depth++;
      else if (template[j] === '}') {
        depth--;
        if (depth === 0) break;
      }
      j++;
    }

    if (depth !== 0) {
      // Unmatched — output literally
      result += template[i++];
      continue;
    }

    const inner = template.slice(i + 1, j);
    i = j + 1;

    // Check for plural/select: {key, type, cases}
    const commaIdx = inner.indexOf(',');
    if (commaIdx !== -1) {
      const key = inner.slice(0, commaIdx).trim();
      const rest = inner.slice(commaIdx + 1).trim();
      const comma2 = rest.indexOf(',');
      if (comma2 !== -1) {
        const type = rest.slice(0, comma2).trim();
        const casesStr = rest.slice(comma2 + 1).trim();
        if (type === 'plural' || type === 'select') {
          const value = vars[key];
          if (value !== undefined) {
            const cases = parseCases(casesStr);
            result += resolvePluralOrSelect(type as 'plural' | 'select', key, value, cases, vars);
            continue;
          }
          result += `{${inner}}`;
          continue;
        }
      }
    }

    // Simple variable {key}
    const key = inner.trim();
    const val = vars[key];
    result += val !== undefined ? String(val) : `{${key}}`;
  }

  return result;
}

// -------------------------------------------------------
// Typed path getter t()
// Usage: t('workitem.state.draft') → 'Borrador'
// -------------------------------------------------------

type Flatten<T, Prefix extends string = ''> = T extends string
  ? Prefix
  : T extends Record<string, unknown>
  ? {
      [K in keyof T & string]: Flatten<T[K], Prefix extends '' ? K : `${Prefix}.${K}`>;
    }[keyof T & string]
  : never;

export type DictKey = Flatten<Dict>;

type DeepGet<T, Path extends string> = Path extends `${infer Head}.${infer Tail}`
  ? Head extends keyof T
    ? DeepGet<T[Head], Tail>
    : never
  : Path extends keyof T
  ? T[Path]
  : never;

export function t<K extends DictKey>(key: K): DeepGet<Dict, K> {
  const parts = key.split('.');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let current: any = es;
  for (const part of parts) {
    if (current == null) return key as DeepGet<Dict, K>;
    current = current[part];
  }
  return (current ?? key) as DeepGet<Dict, K>;
}

// Re-export dictionaries and types
export { common, errors, workitem, review, hierarchy, tags, attachment, lock, mcp, assistant, role };
