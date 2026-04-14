# Spec: Security — US-122

Backend permission enforcement, CORS, rate limiting, input validation, CSRF, CSP, and audit of auth failures.

## Reference decisions

- EP-00: Hybrid JWT (15min access + 30-day refresh), PKCE OAuth
- EP-10: Capability-based permissions (`capabilities[]` on `workspace_member`), Fernet-encrypted credentials, append-only audit log

---

## Scenario 1 — Capability enforcement middleware

WHEN any protected endpoint is invoked
THEN the request passes through `require_capabilities(["capability_name"])` decorator before the handler executes
AND the decorator extracts workspace_id from the route or request body, not from the JWT alone
AND if the authenticated user lacks the required capability in that workspace, the endpoint returns HTTP 403 with body `{"error": {"code": "FORBIDDEN", "message": "Insufficient capabilities"}}`
AND if the workspace_id is missing or invalid, the endpoint returns HTTP 400

WHEN `require_capabilities` is applied to an endpoint
THEN it is enforced unconditionally — no UI-level flag bypass is possible
AND the check occurs after JWT validation and before handler execution in the middleware chain order: JWT auth → rate limit → CORS → capability check → input validation → handler

WHEN a user has `workspace_member.capabilities = ["review"]` and calls an endpoint requiring `["admin"]`
THEN the response is 403 regardless of any other attribute on the user

WHEN a user is a platform superadmin (separate flag, not a capability)
THEN superadmin bypass of capability checks is explicit, logged, and only applies to designated superadmin endpoints

---

## Scenario 2 — JWT authentication

WHEN a request arrives with no Authorization header
THEN the response is HTTP 401 with `{"error": {"code": "UNAUTHORIZED", "message": "Authentication required"}}`

WHEN the access token is expired (>15 minutes)
THEN the response is HTTP 401 with `{"error": {"code": "TOKEN_EXPIRED"}}`
AND the client must use the refresh token endpoint to obtain a new access token

WHEN the refresh token is expired (>30 days) or revoked
THEN the response is HTTP 401 with `{"error": {"code": "REFRESH_EXPIRED"}}`
AND the client redirects to the login page

WHEN a JWT is submitted with an invalid signature
THEN the response is HTTP 401
AND the failure is recorded in the audit log with: timestamp, ip_address, user_agent, token_sub (if decodable), failure_reason

---

## Scenario 3 — CORS policy

WHEN a browser sends a cross-origin request
THEN the server only allows origins present in the `ALLOWED_ORIGINS` environment variable (allowlist)
AND `Access-Control-Allow-Origin` is never set to `*` in any non-development environment
AND credentials (cookies, Authorization headers) are only allowed from allowlisted origins
AND preflight OPTIONS requests return the correct headers with `Access-Control-Max-Age: 600`

WHEN `ALLOWED_ORIGINS` is not configured in a non-development environment
THEN the application refuses to start with a clear configuration error

---

## Scenario 4 — Rate limiting

WHEN any unauthenticated endpoint (login, OAuth callback, token refresh) receives more than 10 requests per minute from the same IP
THEN subsequent requests return HTTP 429 with `Retry-After` header
AND the event is logged with: ip_address, endpoint, request_count, window

WHEN any authenticated API endpoint receives more than 300 requests per minute per user
THEN subsequent requests return HTTP 429
AND the limit resets on a rolling 60-second window (Redis sliding window counter)

WHEN rate limit is applied
THEN response headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` are present on all responses from rate-limited endpoints

---

## Scenario 5 — Input validation

WHEN any request body is received
THEN it is validated against a Pydantic schema before reaching the service layer
AND unknown fields are rejected (Pydantic `model_config = ConfigDict(extra="forbid")`)
AND validation failures return HTTP 422 with field-level error details

WHEN a path or query parameter is received
THEN it is declared with explicit types in FastAPI route signatures (UUID, int, Literal, etc.)
AND no raw string interpolation into SQL queries occurs anywhere in the codebase

WHEN a file upload is received
THEN the file type is validated by content inspection (magic bytes), not by file extension alone
AND the file size is rejected if it exceeds the configured `MAX_UPLOAD_BYTES` limit
AND the filename is sanitized before any filesystem or storage operation

---

## Scenario 6 — CSRF protection

WHEN the frontend makes a state-changing request (POST, PUT, PATCH, DELETE)
THEN the request includes a `X-CSRF-Token` header with a per-session CSRF token
AND the backend validates the token before processing the request
AND CSRF tokens are tied to the session and rotate on each login

WHEN a request lacks the CSRF token on a state-changing endpoint
THEN the response is HTTP 403 with `{"error": {"code": "CSRF_INVALID"}}`
AND the failure is logged

Note: SameSite=Strict cookies mitigate most CSRF risk; explicit CSRF tokens are required for cross-subdomain scenarios.

---

## Scenario 7 — Content Security Policy

WHEN any HTML page is served
THEN the response includes a `Content-Security-Policy` header with at minimum:
  - `default-src 'self'`
  - `script-src 'self'` (no `unsafe-inline`, no `unsafe-eval`)
  - `style-src 'self' 'unsafe-inline'` (Tailwind CSS requires this; document the exception)
  - `img-src 'self' data: https://lh3.googleusercontent.com` (Google avatar images)
  - `connect-src 'self' [Sentry DSN host]`
  - `frame-ancestors 'none'`
AND `X-Frame-Options: DENY` is set for older browser compatibility
AND `X-Content-Type-Options: nosniff` is set on all responses
AND `Referrer-Policy: strict-origin-when-cross-origin` is set

WHEN the application is deployed
THEN CSP violations are reported to a `/api/v1/csp-report` endpoint
AND violation reports are logged at WARN level

---

## Scenario 8 — Secrets handling

WHEN the application starts
THEN all secrets (DB credentials, OAuth client secret, JWT signing key, Fernet key, Sentry DSN, Redis URL) are loaded from environment variables or a secrets manager
AND no secret value appears in source code, git history, or application logs
AND if a required secret is missing at startup, the application exits immediately with a clear error naming the missing variable

WHEN a Jira credential (from EP-10 Fernet-encrypted storage) is loaded for use
THEN it is decrypted in memory, used for the API call, and not stored in any log, error message, or response body

WHEN an error occurs during an external API call
THEN the error log includes: endpoint (without credentials), error type, status code — never the credential values

---

## Scenario 9 — Audit log for sensitive actions

WHEN any of the following actions occurs:
  - user login (success or failure)
  - token refresh
  - permission check failure (403)
  - element status transition (submit, approve, reject, escalate)
  - workspace member role/capability change
  - integration credential creation, update, or deletion
  - export of element data
THEN an audit record is written to the append-only `audit_log` table with:
  - `id` (UUID)
  - `timestamp` (UTC, microsecond precision)
  - `actor_user_id`
  - `workspace_id`
  - `action` (enum string)
  - `target_type` and `target_id`
  - `ip_address`
  - `user_agent`
  - `correlation_id` (from request header)
  - `outcome` (success | failure)
  - `metadata` (JSONB — action-specific detail, NO secrets)

WHEN the audit log write fails
THEN the originating operation is rolled back (audit write is part of the same transaction where applicable)
AND a CRITICAL log entry is emitted

---

## Scenario 10 — OWASP Top 10 baseline

WHEN any SQL query is executed
THEN it uses parameterized queries via SQLAlchemy ORM or Core — raw string interpolation into queries is a hard reject in code review

WHEN any user-supplied string is rendered in HTML
THEN it is escaped by the templating layer — no `dangerouslySetInnerHTML` with unsanitized input

WHEN a redirect URL is constructed from user input
THEN it is validated against an allowlist of internal paths — open redirect is a hard reject

WHEN error responses are returned
THEN stack traces, internal paths, and framework internals are never included in the response body
AND detailed error context is logged server-side only, accessible via correlation ID

WHEN dependencies are updated
THEN `pip-audit` (Python) and `npm audit` (Node) run in CI and block merge on HIGH or CRITICAL CVEs
