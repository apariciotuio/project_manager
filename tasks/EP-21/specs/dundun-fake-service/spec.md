# Spec — Dundun Fake HTTP Service (F-6)

**Capability:** Standalone HTTP service that mimics the Dundun contract for local dev and E2E.

## Scenarios

### Service boots via docker-compose

- **WHEN** the developer runs `docker compose -f docker-compose.dev.yml up dundun-fake`
- **THEN** the service is reachable at `http://localhost:8081` within 5 seconds
- **AND** `GET /health` returns `200` with `{"status": "ok"}`

### Backend uses fake transparently

- **WHEN** `DUNDUN_BASE_URL=http://dundun-fake:8080` is set in `backend/.env`
- **AND** the backend `DundunHttpClient` calls `POST /messages`
- **THEN** the fake accepts the request and returns a synthetic response matching the real Dundun contract
- **AND** no changes to `DundunHttpClient` are required

### POST /messages returns synthetic assistant message

- **WHEN** `POST /messages` is called with `{ thread_id, content, user_id }`
- **THEN** the response is `{ message_id, thread_id, role: "assistant", content, created_at }`
- **AND** the response content is deterministic in `FAKE_MODE=deterministic` (echo + canned phrases)
- **AND** the response content is plausible-looking in `FAKE_MODE=stochastic` (template with random pick)

### Response delay simulates real latency

- **WHEN** `FAKE_MODE=stochastic`
- **THEN** responses delay 300–800ms (jittered) before returning
- **WHEN** `FAKE_MODE=deterministic`
- **THEN** responses delay exactly 100ms

### Error simulation

- **WHEN** the request includes header `X-Fake-Force-Error: 500`
- **THEN** the fake returns `500` with `{ error: { code: "FAKE_FORCED", message: "..." } }`
- **AND** the backend observes the error through the normal error path

### Rate limit simulation

- **WHEN** the request includes header `X-Fake-Force-Error: 429`
- **THEN** the fake returns `429` with a `Retry-After: 2` header

### Reuses existing fake logic

- **WHEN** the fake is implemented
- **THEN** the core response-generation logic lives in or reuses `backend/tests/fakes/fake_dundun_client.py` (DRY — one source of truth)

### Not exposed in production compose

- **WHEN** the developer runs `docker compose -f docker-compose.prod.yml up`
- **THEN** `dundun-fake` is NOT included
- **AND** the production compose file does not reference the fake image

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Fake accidentally deployed to production | Fake service only in `docker-compose.dev.yml` and `docker-compose.e2e.yml`; CI check rejects `dundun-fake` reference in prod compose |
| Fake drifts from real Dundun contract | Contract tests run against both real and fake in CI (when Dundun credentials available); otherwise document contract version in `infra/dundun-fake/CONTRACT.md` |
| Fake becomes a security hole (arbitrary code execution via prompts) | Fake returns canned responses only — no LLM call, no shell-out |
| Persistent state across restarts | Fake is stateless (in-memory dict, wiped on restart) — document explicitly |

## Out of Scope

- Fake for Puppet (separate epic if/when needed)
- Fake for Jira (separate epic)
- Streaming SSE responses (initial fake is single-response POST; stream support added when EP-03 frontend chat lands)
- Multi-turn conversation memory (stateless per-request echo is enough for MVP)
