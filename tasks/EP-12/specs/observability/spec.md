# Spec: Observability — reduced (US-124)

> **Resolved 2026-04-14 (decisions_pending.md #27)**: the full observability stack — Prometheus, Grafana, Loki, OpenTelemetry, Sentry, trace sampling, health dashboards, LLM metrics, `product_events` — is **deferred**. This spec is reduced to stdlib logging + correlation ID only. Everything else previously described here is out of scope for now.

## Scope: stdlib logging + correlation ID only

### Scenario 1 — Correlation ID per request

WHEN a request arrives without an `X-Correlation-ID` header
THEN `CorrelationIDMiddleware` generates a UUID v4 and attaches it to the request state.
AND every log line emitted inside that request handler carries the correlation ID.
AND the response includes the `X-Correlation-ID` header so clients can echo it back.

WHEN a request arrives with an `X-Correlation-ID` header matching `UUID v4`
THEN the middleware reuses that value instead of generating a new one.
AND if the provided value is not a valid UUID, the middleware ignores it and generates a fresh UUID (rejecting is unnecessary; we just refuse to propagate junk).

### Scenario 2 — stdlib logging to stdout

WHEN any log statement is emitted anywhere in the backend
THEN it uses Python's stdlib `logging` module.
AND output goes to stdout (captured by the container runtime; not shipped to an external aggregator).
AND the formatter includes at minimum: timestamp, level, logger name, message, and correlation_id.
AND secrets, credentials, and personally identifiable information beyond `user_id` are NEVER logged.

### Scenario 3 — No external observability stack

WHEN considering Prometheus, Grafana, Loki, OpenTelemetry, Sentry, or a `product_events` table
THEN none are installed, configured, or emitted.
AND no trace sampling, no metrics exporters, no alerting rules.
AND re-introducing them requires a new decision recorded in `decisions_pending.md`.
