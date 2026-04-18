'use client';

import { es } from '@/lib/i18n';

type ErrorPath = string;

/**
 * Resolves an error code to a localized Spanish message.
 * Falls back to generic error for unknown codes.
 * Emits a console.warn for unmapped codes (Sentry hook point).
 */
export function useHumanError(code: ErrorPath): string {
  return resolveErrorMessage(code);
}

export function resolveErrorMessage(code: string): string {
  // Try to resolve from errors dict by path
  const parts = code.split('.');

  // If it starts with 'errors.', strip it for flat lookup
  const lookupParts = parts[0] === 'errors' ? parts.slice(1) : parts;

  let current: any = es.errors;
  for (const part of lookupParts) {
    if (current == null || typeof current !== 'object') {
      current = null;
      break;
    }
    current = current[part];
  }

  if (typeof current === 'string') {
    return current;
  }

  // Also try workitem errors
  let workitemCurrent: any = es.workitem;
  const workitemParts = parts[0] === 'workitem' ? parts.slice(1) : parts;
  for (const part of workitemParts) {
    if (workitemCurrent == null || typeof workitemCurrent !== 'object') {
      workitemCurrent = null;
      break;
    }
    workitemCurrent = workitemCurrent[part];
  }

  if (typeof workitemCurrent === 'string') {
    return workitemCurrent;
  }

  // Unknown code — log for observability
  if (typeof console !== 'undefined') {
    console.warn(`[HumanError] Unmapped error code: "${code}"`);
  }

  return es.errors.generic;
}
