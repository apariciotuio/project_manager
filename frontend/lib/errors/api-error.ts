/**
 * Typed API error with structured envelope support.
 *
 * Re-exports the canonical ApiError from lib/types/auth for convenience.
 * The source of truth lives in lib/types/auth.ts — both locations export
 * the same class.
 */
export { ApiError, type ApiErrorBody } from '@/lib/types/auth';
