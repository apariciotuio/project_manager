# EP-00 Auth Specs — US-001, US-002, US-003

## US-001 — Sign in with Google OAuth

### Happy Path

WHEN an unauthenticated user visits any protected route (e.g. `/`)
THEN the backend responds 401 and the frontend redirects to `/login`

WHEN the user clicks "Sign in with Google" on `/login`
THEN the frontend redirects to `GET /api/v1/auth/google` with a `redirect_uri` pointing to the frontend callback route
AND the backend generates a PKCE code verifier + challenge, stores the verifier in Redis under a short-lived key (5 min TTL), and redirects to Google's OAuth authorization endpoint with `response_type=code`, `scope=openid email profile`, `state` (CSRF token bound to the Redis key), and the PKCE challenge

WHEN Google redirects back to `/api/v1/auth/google/callback?code=<code>&state=<state>`
THEN the backend validates the `state` parameter against the Redis entry (must match and not be expired)
AND the backend exchanges the authorization code for tokens via Google's token endpoint using PKCE verifier
AND the backend extracts `sub`, `email`, `name`, `picture` from the ID token
AND the backend upserts the user record (see US-002)
AND the backend creates a session (see US-003)
AND the backend redirects the user to the frontend at `/` with the session cookie set

### Error Cases

WHEN Google OAuth returns `error=access_denied` (user cancelled)
THEN the backend redirects to `/login?error=cancelled`
AND no session is created

WHEN the `state` parameter is missing or does not match the Redis entry
THEN the backend responds 400 and redirects to `/login?error=invalid_state`
AND the event is logged at WARN level with IP and timestamp

WHEN the `state` key has expired in Redis (>5 min)
THEN the backend responds 400 and redirects to `/login?error=state_expired`

WHEN Google's token exchange fails (network error, invalid code)
THEN the backend responds 502 and redirects to `/login?error=provider_error`
AND the error is logged at ERROR level with the upstream status

WHEN the Google ID token cannot be verified (invalid signature, wrong audience, expired)
THEN the backend responds 401 and redirects to `/login?error=token_invalid`

### Edge Cases

WHEN the user initiates OAuth but closes the browser tab before completing
THEN the Redis state key expires naturally after 5 min
AND no session or user record is created

WHEN the same Google account signs in from two browser tabs simultaneously
THEN both flows complete independently
AND only one user record exists (upserted, not duplicated)

WHEN Google returns a different `email` for the same `sub` (rare but possible after account changes)
THEN the user is resolved by `sub` (primary key from Google), email is updated
AND a WARN audit log entry is emitted noting the email change

---

## US-002 — Create or Resolve Unique User Profile

### Happy Path

WHEN a new Google account authenticates for the first time
THEN the backend inserts a `users` record with:
  - `google_sub` (Google's `sub` claim, the authoritative identifier)
  - `email`
  - `full_name`
  - `avatar_url` (Google `picture` claim)
  - `created_at`, `updated_at`
  - `status = active`
AND returns the created user object with a system-generated UUID as `id`

WHEN a returning user authenticates (same `google_sub` already in DB)
THEN the backend updates `email`, `full_name`, `avatar_url` if they differ from the stored values
AND `updated_at` is refreshed
AND the existing `id` is preserved
AND `status` is not changed by this process

### Error Cases

WHEN two concurrent requests attempt to insert the same `google_sub`
THEN the DB upsert (INSERT ... ON CONFLICT DO UPDATE) handles it atomically
AND exactly one record exists after both requests complete

WHEN the `email` field from Google is missing (Google returns no email claim)
THEN the authentication flow fails with 422
AND the user is redirected to `/login?error=email_required`

WHEN the `google_sub` value changes for a known email (extremely rare, Google account migration)
THEN a new user record is created for the new `sub`
AND the old record is NOT merged or deleted automatically
AND this is logged at ERROR for manual review

### Edge Cases

WHEN a user's Google avatar URL becomes a 404 (deleted profile picture)
THEN the system stores the URL as-is
AND the frontend handles broken image gracefully (fallback to initials)

WHEN `full_name` is null or empty in the Google response
THEN `email` local part (before `@`) is used as display name
AND `full_name` is stored as that derived value

---

## US-003 — Manage Session and Protected Route Access

### Session Creation

WHEN authentication succeeds (US-001 flow completes)
THEN the backend creates a JWT access token signed with HS256 (secret from env with documented rotation) containing:
  - `sub`: user UUID
  - `email`
  - `workspace_id`: resolved default workspace ID (may be null on very first login before bootstrap)
  - `iat`, `exp` (15 min TTL)
AND creates a refresh token (opaque, 32-byte random, stored as a hash in `sessions` table) with 30-day TTL
AND sets two HTTP-only, Secure, SameSite=Lax cookies:
  - `access_token` (15 min, path=/)
  - `refresh_token` (30 days, path=/api/v1/auth/refresh)

### Protected Route Access

WHEN an authenticated request arrives with a valid `access_token` cookie
THEN the backend middleware verifies the JWT signature and expiry
AND injects the decoded user identity into the request context
AND the request proceeds to the handler

WHEN an authenticated request arrives with an expired `access_token` but valid `refresh_token`
THEN the backend issues a new `access_token` (silent refresh via `/api/v1/auth/refresh`)
AND sets the new `access_token` cookie
AND the original request is retried transparently by the middleware (or frontend interceptor)

WHEN the `refresh_token` is expired or revoked
THEN the backend responds 401 with body `{"error": {"code": "SESSION_EXPIRED", "message": "Session expired"}}`
AND both cookies are cleared
AND the frontend redirects to `/login`

WHEN a request arrives with no auth cookies
THEN the backend responds 401 with body `{"error": {"code": "UNAUTHENTICATED", "message": "Authentication required"}}`
AND the frontend redirects to `/login`

WHEN a request arrives with a structurally invalid JWT (tampered, wrong signature)
THEN the backend responds 401 with body `{"error": {"code": "INVALID_TOKEN", "message": "Invalid token"}}`
AND the event is logged at WARN with IP and token fragment (first 8 chars only, never full token)

### Logout

WHEN the user calls `POST /api/v1/auth/logout`
THEN the backend revokes the refresh token (deletes the `sessions` record or marks `revoked_at`)
AND clears both cookies (Set-Cookie with Max-Age=0)
AND responds 204
AND the logout event is written to the audit log

### Audit Log Requirements

WHEN any of these events occur: login_success, login_failure, logout, token_refresh, session_expired, invalid_token_attempt
THEN the backend writes a structured log entry containing:
  - `event_type`
  - `user_id` (if known)
  - `ip_address`
  - `user_agent`
  - `timestamp` (UTC ISO 8601)
  - `outcome` (success | failure)
  - `details` (error code if failure)
AND the log entry does NOT contain the full token or any secret material

### GET /api/v1/auth/me

WHEN an authenticated user calls `GET /api/v1/auth/me`
THEN the backend responds 200 with:
```json
{
  "data": {
    "id": "<uuid>",
    "email": "user@example.com",
    "full_name": "User Name",
    "avatar_url": "https://...",
    "workspace_id": "<uuid>"
  }
}
```

WHEN an unauthenticated user calls `GET /api/v1/auth/me`
THEN the backend responds 401
