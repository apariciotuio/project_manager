import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_PATHS = ['/login', '/favicon.ico'];
// `/api/v1/auth/` is excluded by `config.matcher` below — no need to list here.
const PUBLIC_PREFIXES = ['/_next/'];

const IS_DEV = process.env.NODE_ENV !== 'production';

// connect-src covers fetch, EventSource (SSE), and WebSocket.
// In prod, 'self' covers same-origin SSE to /api/v1/jobs/{id}/progress and other streaming endpoints.
// In dev, ws: allows HMR WebSocket.
const CSP = [
  "default-src 'self'",
  IS_DEV
    ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    : "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://lh3.googleusercontent.com",
  "font-src 'self'",
  IS_DEV
    ? "connect-src 'self' ws: http://localhost:* http://127.0.0.1:*"
    : "connect-src 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  'report-uri /api/v1/csp-report',
].join('; ');

function applySecurityHeaders(response: NextResponse): NextResponse {
  response.headers.set('content-security-policy', CSP);
  response.headers.set('x-frame-options', 'DENY');
  response.headers.set('x-content-type-options', 'nosniff');
  response.headers.set('referrer-policy', 'strict-origin-when-cross-origin');
  return response;
}

function isPublic(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname, search } = request.nextUrl;

  if (isPublic(pathname)) {
    return applySecurityHeaders(NextResponse.next());
  }

  const hasToken = request.cookies.has('access_token');
  if (!hasToken) {
    const returnTo = encodeURIComponent(`${pathname}${search}`);
    const redirect = NextResponse.redirect(
      new URL(`/login?returnTo=${returnTo}`, request.url),
    );
    return applySecurityHeaders(redirect);
  }

  return applySecurityHeaders(NextResponse.next());
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|api/).*)',
  ],
};
