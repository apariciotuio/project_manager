import { describe, it, expect } from 'vitest';
import { middleware, config } from '@/middleware';
import { NextRequest } from 'next/server';

function makeRequest(
  path: string,
  cookies: Record<string, string> = {},
): NextRequest {
  const url = `http://localhost${path}`;
  const req = new NextRequest(url);
  Object.entries(cookies).forEach(([name, value]) => {
    req.cookies.set(name, value);
  });
  return req;
}

describe('middleware', () => {
  it('redirects unauthenticated request to protected path → /login with returnTo', () => {
    const req = makeRequest('/workspace/acme/work-items');
    const res = middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get('location') ?? '';
    expect(location).toContain('/login');
    expect(location).toContain('returnTo=');
    expect(decodeURIComponent(location)).toContain(
      '/workspace/acme/work-items',
    );
  });

  it('passes through authenticated request with access_token cookie', () => {
    const req = makeRequest('/workspace/acme', {
      access_token: 'some-token',
    });
    const res = middleware(req);
    // next() response does not have a redirect status
    expect(res.status).not.toBe(307);
    expect(res.status).not.toBe(302);
  });

  it('always allows /login regardless of cookie state', () => {
    const req = makeRequest('/login');
    const res = middleware(req);
    expect(res.status).not.toBe(307);
  });

  it('matcher config excludes all API routes', () => {
    const matchers = config.matcher as string[];
    expect(matchers[0]).toContain('api/');
  });

  it('returnTo encodes the full path', () => {
    const req = makeRequest('/workspace/acme/items?q=test');
    const res = middleware(req);
    const location = res.headers.get('location') ?? '';
    expect(decodeURIComponent(location)).toContain(
      '/workspace/acme/items?q=test',
    );
  });
});
