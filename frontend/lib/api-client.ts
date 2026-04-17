/**
 * Fetch wrapper with:
 * - Correlation-id header injection
 * - Typed helpers: apiGet, apiPost, apiPatch, apiDelete
 * - Auto-refresh on 401 (single retry, concurrent-safe)
 * - Typed ApiError / UnauthenticatedError
 *
 * Uses relative URLs in browser (Next.js rewrites proxy /api/v1/* to backend).
 * In test/node env, NEXT_PUBLIC_API_BASE_URL=http://localhost makes paths absolute.
 */
import { ApiError, UnauthenticatedError } from './types/auth';
import type { ApiErrorBody } from './types/auth';

// In browser: NEXT_PUBLIC_API_BASE_URL is '' so fetch uses relative paths (proxied by Next.js).
// In tests: vitest sets NEXT_PUBLIC_API_BASE_URL=http://localhost so MSW can intercept absolute URLs.
const API_BASE = process.env['NEXT_PUBLIC_API_BASE_URL'] ?? '';

export { ApiError, UnauthenticatedError } from './types/auth';

// --- Refresh concurrency guard ---
let refreshPromise: Promise<void> | null = null;

function generateCorrelationId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

async function parseErrorBody(response: Response): Promise<ApiErrorBody> {
  try {
    const json = (await response.json()) as {
      error?: Partial<ApiErrorBody>;
      message?: string;
    };
    if (json.error && typeof json.error.code === 'string') {
      return {
        code: json.error.code,
        message: json.error.message ?? response.statusText,
        details: json.error.details,
      };
    }
  } catch {
    // fall through
  }
  return {
    code: String(response.status),
    message: response.statusText || `HTTP ${response.status}`,
  };
}

async function doRefresh(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-Id': generateCorrelationId(),
    },
    credentials: 'include',
  });
  if (res.status === 401) {
    throw new UnauthenticatedError();
  }
  if (!res.ok) {
    const body = await parseErrorBody(res);
    throw new ApiError(res.status, body);
  }
}

async function refreshOnce(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

const REFRESH_PATH = '/api/v1/auth/refresh';

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  isRetry = false,
): Promise<T> {
  const correlationId = generateCorrelationId();
  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-Id': correlationId,
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, init);

  if (response.ok) {
    // 204 No Content — return undefined (void responses)
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  // 401 handling: attempt refresh once, then retry
  if (response.status === 401 && !isRetry && path !== REFRESH_PATH) {
    await refreshOnce();
    return request<T>(method, path, body, true);
  }

  // 401 on retry or on refresh endpoint itself
  if (response.status === 401) {
    throw new UnauthenticatedError();
  }

  const errorBody = await parseErrorBody(response);
  throw new ApiError(response.status, errorBody);
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>('PATCH', path, body);
}

export async function apiDelete<T>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}
