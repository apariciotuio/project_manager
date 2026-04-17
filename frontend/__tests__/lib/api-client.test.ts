import { describe, it, expect, beforeEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../msw/server';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import { ApiError, UnauthenticatedError } from '@/lib/types/auth';

// api-client uses relative paths; MSW intercepts them as-is in node mode
const BASE = 'http://localhost';

describe('apiGet', () => {
  it('returns parsed JSON on 200', async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json({ data: 'ok' }),
      ),
    );
    const result = await apiGet<{ data: string }>('/api/v1/test');
    expect(result).toEqual({ data: 'ok' });
  });

  it('throws ApiError on 403', async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'Forbidden' } },
          { status: 403 },
        ),
      ),
    );
    await expect(apiGet('/api/v1/test')).rejects.toBeInstanceOf(ApiError);
  });

  it('throws ApiError on 404', async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Not found' } },
          { status: 404 },
        ),
      ),
    );
    const err = await apiGet('/api/v1/test').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
  });

  it('throws ApiError on 500', async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json(
          { error: { code: 'SERVER_ERROR', message: 'Oops' } },
          { status: 500 },
        ),
      ),
    );
    const err = await apiGet('/api/v1/test').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(500);
  });

  it('does NOT call refresh on 403/404/500', async () => {
    let refreshCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'no' } },
          { status: 403 },
        ),
      ),
      http.post(`${BASE}/api/v1/auth/refresh`, () => {
        refreshCalled = true;
        return HttpResponse.json({}, { status: 200 });
      }),
    );
    await apiGet('/api/v1/test').catch(() => {});
    expect(refreshCalled).toBe(false);
  });
});

describe('401 retry / refresh flow', () => {
  it('calls refresh on 401, retries original, returns success', async () => {
    let attempts = 0;
    server.use(
      http.get(`${BASE}/api/v1/protected`, () => {
        attempts++;
        if (attempts === 1) {
          return HttpResponse.json(
            { error: { code: 'UNAUTHORIZED', message: 'no' } },
            { status: 401 },
          );
        }
        return HttpResponse.json({ data: 'secret' });
      }),
      http.post(`${BASE}/api/v1/auth/refresh`, () =>
        HttpResponse.json({ data: 'refreshed' }),
      ),
    );
    const result = await apiGet<{ data: string }>('/api/v1/protected');
    expect(result).toEqual({ data: 'secret' });
    expect(attempts).toBe(2);
  });

  it('throws UnauthenticatedError when retry after refresh also returns 401', async () => {
    let refreshCount = 0;
    server.use(
      http.get(`${BASE}/api/v1/protected`, () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'no' } },
          { status: 401 },
        ),
      ),
      http.post(`${BASE}/api/v1/auth/refresh`, () => {
        refreshCount++;
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    await expect(apiGet('/api/v1/protected')).rejects.toBeInstanceOf(
      UnauthenticatedError,
    );
    expect(refreshCount).toBe(1);
  });

  it('does NOT call refresh on the refresh endpoint itself (no loop)', async () => {
    let refreshCount = 0;
    server.use(
      http.post(`${BASE}/api/v1/auth/refresh`, () => {
        refreshCount++;
        return HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'no' } },
          { status: 401 },
        );
      }),
    );
    await expect(apiPost('/api/v1/auth/refresh', {})).rejects.toBeInstanceOf(
      UnauthenticatedError,
    );
    expect(refreshCount).toBe(1);
  });

  it('concurrent 401s wait on single refresh, not multiple', async () => {
    let refreshCount = 0;
    let callCount = 0;
    server.use(
      http.get(`${BASE}/api/v1/protected`, () => {
        callCount++;
        if (callCount <= 2) {
          return HttpResponse.json(
            { error: { code: 'UNAUTHORIZED', message: 'no' } },
            { status: 401 },
          );
        }
        return HttpResponse.json({ data: 'ok' });
      }),
      http.post(`${BASE}/api/v1/auth/refresh`, () => {
        refreshCount++;
        return HttpResponse.json({ data: 'ok' });
      }),
    );
    // Fire two concurrent requests that both get 401
    const [r1, r2] = await Promise.all([
      apiGet('/api/v1/protected'),
      apiGet('/api/v1/protected'),
    ]);
    expect(r1).toEqual({ data: 'ok' });
    expect(r2).toEqual({ data: 'ok' });
    expect(refreshCount).toBe(1);
  });
});

describe('apiPost', () => {
  it('sends POST with body and returns parsed JSON', async () => {
    server.use(
      http.post(`${BASE}/api/v1/items`, async ({ request }) => {
        const body = await request.json();
        return HttpResponse.json({ data: body });
      }),
    );
    const result = await apiPost<{ data: unknown }>('/api/v1/items', {
      name: 'test',
    });
    expect(result).toEqual({ data: { name: 'test' } });
  });
});

describe('apiPatch', () => {
  it('sends PATCH with body and returns parsed JSON', async () => {
    server.use(
      http.patch(`${BASE}/api/v1/items/1`, async ({ request }) => {
        const body = await request.json();
        return HttpResponse.json({ data: body });
      }),
    );
    const result = await apiPatch<{ data: unknown }>('/api/v1/items/1', {
      name: 'updated',
    });
    expect(result).toEqual({ data: { name: 'updated' } });
  });
});

describe('apiDelete', () => {
  it('sends DELETE and returns parsed JSON', async () => {
    server.use(
      http.delete(`${BASE}/api/v1/items/1`, () =>
        HttpResponse.json({ data: null }),
      ),
    );
    const result = await apiDelete<{ data: null }>('/api/v1/items/1');
    expect(result).toEqual({ data: null });
  });
});
