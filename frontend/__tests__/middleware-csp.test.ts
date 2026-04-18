import { describe, it, expect } from 'vitest';
import { middleware } from '@/middleware';
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

describe('middleware — CSP and security headers', () => {
  it('sets Content-Security-Policy header on authenticated HTML response', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    const csp = res.headers.get('content-security-policy');
    expect(csp).not.toBeNull();
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("style-src 'self' 'unsafe-inline'");
    expect(csp).toContain("img-src 'self' data: https://lh3.googleusercontent.com");
    expect(csp).toContain("frame-ancestors 'none'");
  });

  it('sets Content-Security-Policy header on public paths (login)', () => {
    const req = makeRequest('/login');
    const res = middleware(req);
    const csp = res.headers.get('content-security-policy');
    expect(csp).not.toBeNull();
    expect(csp).toContain("default-src 'self'");
  });

  it('CSP contains report-uri pointing to /api/v1/csp-report', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    const csp = res.headers.get('content-security-policy');
    expect(csp).toContain('report-uri /api/v1/csp-report');
  });

  it('sets X-Frame-Options: DENY', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    expect(res.headers.get('x-frame-options')).toBe('DENY');
  });

  it('sets X-Content-Type-Options: nosniff', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    expect(res.headers.get('x-content-type-options')).toBe('nosniff');
  });

  it('sets Referrer-Policy: strict-origin-when-cross-origin', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    expect(res.headers.get('referrer-policy')).toBe(
      'strict-origin-when-cross-origin',
    );
  });

  it('CSP does not contain unsafe-eval in script-src', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    const csp = res.headers.get('content-security-policy') ?? '';
    // Extract script-src directive value only
    const scriptSrc =
      csp
        .split(';')
        .find((d) => d.trim().startsWith('script-src')) ?? '';
    expect(scriptSrc).not.toContain('unsafe-eval');
    expect(scriptSrc).not.toContain("'unsafe-inline'");
  });

  it('also sets security headers on redirect responses', () => {
    const req = makeRequest('/workspace/acme'); // no token → redirect
    const res = middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get('x-frame-options')).toBe('DENY');
    expect(res.headers.get('content-security-policy')).not.toBeNull();
  });

  it('CSP includes connect-src with self (covers same-origin fetch, EventSource, WebSocket)', () => {
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    const csp = res.headers.get('content-security-policy') ?? '';
    expect(csp).toContain("connect-src 'self'");
  });

  it('CSP connect-src in dev includes ws: for HMR', () => {
    // Note: In test env, process.env.NODE_ENV is controlled by vitest config.
    // This test documents expected behavior but may not execute if NODE_ENV is 'test'.
    // The actual dev CSP is tested in a real dev build or via env override.
    const req = makeRequest('/workspace/acme', { access_token: 'tok' });
    const res = middleware(req);
    const csp = res.headers.get('content-security-policy') ?? '';
    // If NODE_ENV is 'production' in test, this will skip the ws: check.
    // In CI, NODE_ENV should be 'test' and this will verify the dev CSP pattern.
    if (process.env.NODE_ENV !== 'production') {
      expect(csp).toContain('ws:');
    }
  });
});
