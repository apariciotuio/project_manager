/**
 * Client-safe environment accessors.
 * Only NEXT_PUBLIC_* vars are available in the browser.
 */

export const env = {
  apiBaseUrl:
    process.env['NEXT_PUBLIC_API_BASE_URL'] ?? 'http://localhost:17004',
  defaultLocale: process.env['NEXT_PUBLIC_DEFAULT_LOCALE'] ?? 'es',
} as const;
