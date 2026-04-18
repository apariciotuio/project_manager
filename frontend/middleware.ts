import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_PATHS = ['/login', '/favicon.ico'];
// `/api/v1/auth/` is excluded by `config.matcher` below — no need to list here.
const PUBLIC_PREFIXES = ['/_next/'];

const IS_DEV = process.env.NODE_ENV !== 'production';

/**
 * Decode a JWT payload without verifying the signature.
 * Returns the `exp` field (seconds since epoch) or null if the token is not
 * a well-formed JWT or has no `exp` claim.
 *
 * We only need `exp` — signature verification is the backend's job.
 * Middleware runs at the edge (Node.js-compatible runtime), so we use
 * `atob` (available in the Next.js edge runtime and in jsdom for tests).
 */
function jwtExp(token: string): number | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  const payloadPart = parts[1];
  if (!payloadPart) return null;
  try {
    const padded = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = atob(padded);
    const payload = JSON.parse(decoded) as Record<string, unknown>;
    if (typeof payload['exp'] === 'number') return payload['exp'];
    return null;
  } catch {
    return null;
  }
}

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

  const tokenValue = request.cookies.get('access_token')?.value;

  if (!tokenValue) {
    const returnTo = encodeURIComponent(`${pathname}${search}`);
    const redirect = NextResponse.redirect(
      new URL(`/login?returnTo=${returnTo}`, request.url),
    );
    return applySecurityHeaders(redirect);
  }

  // Check JWT expiry. Three cases:
  //   1. Decodable JWT with exp in the future → pass through.
  //   2. Decodable JWT with exp in the past → redirect with reauth=true (user had a session, it expired).
  //   3. Not a valid JWT (opaque token, malformed) → redirect as unauthenticated (no reauth flag).
  //      The backend will issue a proper JWT on the next OAuth round-trip.
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = jwtExp(tokenValue);

  if (exp === null) {
    // Not a JWT we can inspect — treat as unauthenticated.
    const returnTo = encodeURIComponent(`${pathname}${search}`);
    const redirect = NextResponse.redirect(
      new URL(`/login?returnTo=${returnTo}`, request.url),
    );
    return applySecurityHeaders(redirect);
  }

  if (exp < nowSec) {
    const returnTo = encodeURIComponent(`${pathname}${search}`);
    const redirect = NextResponse.redirect(
      new URL(`/login?reauth=true&returnTo=${returnTo}`, request.url),
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
