# Spec: Observability — US-124

Structured log format, correlation ID propagation, error tracking, product event taxonomy, operational monitoring.

---

## Scenario 1 — Structured JSON log format

WHEN any log statement is emitted anywhere in the backend
THEN it is serialized as a single-line JSON object (no multi-line logs)
AND it contains at minimum the following fields:
  ```json
  {
    "timestamp": "2026-04-13T10:23:45.123456Z",
    "level": "INFO",
    "logger": "app.services.element_service",
    "message": "Element status transitioned",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "usr_abc123",
    "workspace_id": "ws_xyz789",
    "duration_ms": 47,
    "environment": "production"
  }
  ```
AND additional context fields are allowed (no schema restriction on extras)
AND secrets, credentials, PII beyond user_id, and stack traces are NEVER present in the message field

WHEN an exception is logged
THEN the `exception` field contains: `{"type": "ValueError", "message": "...", "traceback": "<single-line escaped traceback>"}`
AND the full traceback is included in the `exception.traceback` field, not in `message`

WHEN a log statement is emitted at DEBUG level in production
THEN it is suppressed unless `LOG_LEVEL=DEBUG` is explicitly set
AND DEBUG logs must never contain secrets under any log level

---

## Scenario 2 — Correlation ID propagation

WHEN an HTTP request arrives at the API
THEN the middleware checks for an `X-Correlation-ID` header
AND if present, it is validated as a valid UUID and used as the correlation_id for all logs in that request
AND if absent, a new UUID v4 is generated and used
AND the correlation_id is set in response header `X-Correlation-ID`

WHEN the application dispatches a Celery task
THEN the correlation_id from the originating request is passed as a task header
AND the Celery worker retrieves it and injects it into the task's logging context

WHEN the application makes an outbound HTTP call (to Jira, to OAuth provider, etc.)
THEN the `X-Correlation-ID` header is included in the outbound request

WHEN an error is reported to Sentry
THEN the correlation_id is set as a Sentry tag so it is searchable in the Sentry UI

WHEN the frontend makes an API request
THEN it generates a UUID v4 per-request and sends it as `X-Correlation-ID`
AND on error display, the correlation_id is shown to the user as a reference code: "Error reference: [correlation_id]"

---

## Scenario 3 — Sentry error tracking integration

WHEN an unhandled exception occurs in the backend
THEN it is automatically captured by the Sentry SDK and sent to the Sentry project
AND the Sentry event includes: correlation_id (tag), user_id, workspace_id, environment, release version

WHEN a handled error is explicitly reported (e.g., integration failure, audit log write failure)
THEN `sentry_sdk.capture_exception()` is called with extra context: `{"correlation_id": "...", "workspace_id": "..."}`

WHEN an unhandled error reaches the React ErrorBoundary in the frontend
THEN it is captured by the Sentry browser SDK
AND the Sentry event includes: correlation_id, user_id, route path, component stack

WHEN a Sentry event is triggered
THEN it is deduplicated by fingerprint (same exception class + same code location = same issue)
AND alerts are configured to fire on Slack/PagerDuty for new issues and for issues with >10 occurrences/hour

WHEN the Sentry DSN is not configured
THEN the application starts normally with a WARNING log
AND errors are still logged to stdout — Sentry is non-blocking

---

## Scenario 4 — Product event taxonomy

WHEN a product event occurs, it is tracked via the `ProductEventService` adapter
AND each event has the canonical schema:
  ```json
  {
    "event": "element.submitted",
    "timestamp": "2026-04-13T10:23:45Z",
    "user_id": "usr_abc123",
    "workspace_id": "ws_xyz789",
    "properties": { ... }
  }
  ```

### Required events and their `properties`

| Event name | Trigger | Properties |
|------------|---------|------------|
| `user.login` | Successful OAuth login | `method: "google"` |
| `user.login_failed` | Failed auth attempt | `reason: "invalid_token"` |
| `element.created` | Element created | `element_type`, `source: "manual|import"` |
| `element.submitted` | Submitted for review | `element_type`, `assignee_id` |
| `element.reviewed` | Review action taken | `element_type`, `outcome: "approved|rejected|changes_requested"` |
| `element.exported` | Export triggered | `element_type`, `format: "csv|pdf"`, `count` |
| `search.performed` | Search executed | `query_length` (NOT the query text), `result_count` |
| `integration.synced` | Jira sync completed | `integration_type: "jira"`, `items_synced`, `duration_ms` |
| `integration.failed` | Jira sync failed | `integration_type: "jira"`, `error_code` |
| `workspace.member_invited` | Member invited | `capabilities` |
| `workspace.member_removed` | Member removed | (no extra properties) |

WHEN a product event is tracked
THEN user PII beyond user_id and workspace_id is NOT included in properties
AND query text, element content, and file names are NOT tracked in events

WHEN the analytics backend (e.g., Segment, PostHog, or internal append log) is unavailable
THEN event tracking failures do NOT propagate exceptions to the caller
AND missed events are logged at WARN level with the event name and correlation_id

---

## Scenario 5 — Integration failure visibility

WHEN a Jira sync operation fails (any step)
THEN an `integration.failed` event is emitted
AND the failure is recorded in the `integration_sync_log` table with: `workspace_id`, `integration_id`, `error_code`, `error_message`, `timestamp`, `retry_count`

WHEN the admin dashboard is loaded for a workspace
THEN the integration health section shows: last sync time, last sync status (success/failure), consecutive failure count
AND if the last 3 consecutive syncs have failed, a warning banner is shown: "Jira sync is failing. Check your credentials."

WHEN an integration credential becomes invalid (Jira returns 401)
THEN the workspace admin receives an in-app notification (SSE, EP-08 pattern)
AND the integration is marked as `status: "credential_error"` in the DB
AND subsequent sync attempts are skipped until the credential is updated

---

## Scenario 6 — Operational monitoring dashboard

The monitoring dashboard is built on top of the structured logs and product events. It does NOT require a paid APM tool for MVP — it can be built from Postgres + Redis metrics + log aggregation.

WHEN the ops team opens the monitoring dashboard
THEN they see:
  - Request rate (requests/min) broken down by endpoint
  - p50 / p95 response time per endpoint (last 5 minutes)
  - Error rate (5xx/4xx counts per minute)
  - Active users (distinct user_ids with requests in last 5 minutes)
  - Celery queue depths per queue (high/default/low)
  - Redis memory usage %
  - Integration health per workspace (last sync status, failure streak)

WHEN an endpoint's p95 latency exceeds the target from the performance spec for 3 consecutive minutes
THEN an alert fires to the ops channel

WHEN the error rate exceeds 1% of requests for 2 consecutive minutes
THEN an alert fires with: error_rate, top_error_types, sample correlation_ids

---

## Scenario 7 — Adoption metrics

WHEN the product team queries adoption data
THEN they can retrieve from the product events log:
  - Daily/weekly active users (DAU/WAU) per workspace
  - Elements created per workspace per day
  - Review cycle time: median time from `element.submitted` to `element.reviewed`
  - Search usage rate (% of sessions with a search)
  - Integration sync success rate per workspace

WHEN the product events log is queried
THEN queries are against a read-optimized materialized view refreshed every 15 minutes
AND direct queries against the production DB for analytics are NOT allowed

---

## Scenario 8 — Log retention and access

WHEN logs are written to stdout (default container logging)
THEN they are captured by the container orchestrator and forwarded to the log aggregation system
AND logs are retained for minimum 30 days
AND access to production logs is restricted to the ops team and authorized developers

WHEN a developer needs to investigate an incident
THEN they can search logs by correlation_id across all services and find all related log lines within 10 seconds
