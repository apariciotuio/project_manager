import { describe, it, expect } from 'vitest';
import { middleware, config } from '@/middleware';
import { NextRequest } from 'next/server';

// Build a minimal JWT-shaped token with the given exp (seconds since epoch).
// We only encode the payload — middleware only needs to read `exp`, no signature check.
function makeJwt(exp: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  const payload = btoa(JSON.stringify({ sub: 'user-1', exp }))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  return `${header}.${payload}.fake-sig`;
}

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

const FUTURE_EXP = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
const PAST_EXP = Math.floor(Date.now() / 1000) - 60; // 1 minute ago

describe('middleware — auth gate', () => {
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

  it('passes through authenticated request with valid access_token cookie', () => {
    const req = makeRequest('/workspace/acme', {
      access_token: makeJwt(FUTURE_EXP),
    });
    const res = middleware(req);
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

  it('returnTo encodes the full path including query string', () => {
    const req = makeRequest('/workspace/acme/items?q=test');
    const res = middleware(req);
    const location = res.headers.get('location') ?? '';
    expect(decodeURIComponent(location)).toContain(
      '/workspace/acme/items?q=test',
    );
  });

  // F-1: workspace picker is included in the auth gate
  it('redirects unauthenticated request to workspace picker → /login with returnTo', () => {
    const req = makeRequest('/workspace/select');
    const res = middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get('location') ?? '';
    expect(location).toContain('/login');
    expect(decodeURIComponent(location)).toContain('/workspace/select');
  });

  it('passes through authenticated request to workspace picker', () => {
    const req = makeRequest('/workspace/select', {
      access_token: makeJwt(FUTURE_EXP),
    });
    const res = middleware(req);
    expect(res.status).not.toBe(307);
    expect(res.status).not.toBe(302);
  });

  // F-1: expired token → redirect with reauth=true
  it('redirects expired token to /login with reauth=true and returnTo', () => {
    const req = makeRequest('/workspace/acme/items', {
      access_token: makeJwt(PAST_EXP),
    });
    const res = middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get('location') ?? '';
    expect(location).toContain('/login');
    expect(location).toContain('reauth=true');
    expect(decodeURIComponent(location)).toContain('/workspace/acme/items');
  });

  it('redirects expired token on workspace picker to /login with reauth=true', () => {
    const req = makeRequest('/workspace/select', {
      access_token: makeJwt(PAST_EXP),
    });
    const res = middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get('location') ?? '';
    expect(location).toContain('reauth=true');
  });

  // F-1: malformed / opaque token (not a JWT) → treat as unauthenticated (no reauth flag)
  it('redirects opaque/non-JWT token without reauth flag', () => {
    const req = makeRequest('/workspace/acme', {
      access_token: 'not-a-jwt',
    });
    const res = middleware(req);
    expect(res.status).toBe(307);
    const location = res.headers.get('location') ?? '';
    expect(location).toContain('/login');
    expect(location).not.toContain('reauth=true');
  });
});
