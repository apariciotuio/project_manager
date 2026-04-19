# EP-18 — v2 Carveout

**Closed as MVP-complete 2026-04-19** with the following capabilities deliberately punted to v2:

- **Cap 2** — SDK scaffolding (Python/TypeScript clients)
- **Cap 3** — k8s deployment + helm chart
- **Cap 4** — middleware hardening (rate limit per-token, structured logging enrichment, request/response audit)
- **Cap 5** — Prometheus metrics + OTel tracing on every tool call

MVP scope shipped (Cap 1): 11 read tools end-to-end + `mcp_token` lifecycle (issue/verify/rotate/revoke) + admin REST + opaque token verify in the MCP server. ~210 tests.

These caps are operational concerns, not core product. Track as an operational epic once we have real production usage data to size middleware + metric cardinality.
