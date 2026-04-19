# EP-03 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Core Clarification, Conversation & Assisted Actions shipped: ChatPanel with WS send/recv, ConversationService + ThreadService, suggestion apply path (with atomicity tests), Dundun callback (10 integration tests), RLS on `conversation_threads` / `assistant_suggestions` / `gap_findings` (migration 0033), MF-2 WS bridge refactor with send/recv regression tests.

## EP-04 dependent (cross-epic scope)

- **`QuickActionService` (Phase 6+)** — execute + undo (`tasks-backend.md` line 254).
- **`POST /work-items/{id}/quick-actions` + `.../undo`** (`tasks-backend.md` line 312).
- **`POST /work-items/{id}/gaps/ai-review`** (`tasks-backend.md` line 313).
- **Section pulse animation consumer** (`tasks-frontend.md` Phase 3/D, SpecificationSectionsEditor).
- **`ChatPanel` ↔ "Apply this change" in `suggestion_card`** — Dundun schema lacks the `suggestion_card` WS frame today.
- **WorkItemDetailLayout full integration** — requires EP-04 `SpecificationPanel` + EP-05 task tree slots.

## Cross-epic ownership

- **SSE stream client** — EP-12 owns the SSE contract; EP-03 uses WS per decision #17.
- **`ClarificationQuestion` standalone component** — superseded; ChatPanel handles Q&A via WS.

## Security Should-Fix deferrals (low risk)

- **SF #6 — Outstanding `request_id` binding** — HMAC + idempotency (`get_by_dundun_request_id`) already in place; adds `suggestion_requests` stub table later if needed (`tasks-backend.md` line 416).
- **SF #7 — JWT-in-query-param logging** — needs short-lived WS token or subprotocol auth; deferred to EP-12 observability scope (`tasks-backend.md` line 417).
- **SF #8 — `JwtAdapter` per WS connection** — minor perf polish via FastAPI Depends (`tasks-backend.md` line 418).
- **SF #9 — Service private-attribute access from controllers** — clean-up, not a defect (`tasks-backend.md` line 419).

## QA gates

- **WS proxy manual E2E against a Dundun stub** — unit-level regression covers `bridge.send()` + `bridge.recv()` (`TestChatWs` in `test_dundun_http_client.py`); end-to-end requires a running Dundun stub.
- **Zod runtime validation of API responses** — runtime schema validation was scoped out per design.md; errors manifest in tests only today.

---

MVP scope (ChatPanel, conversation threads, suggestion apply with atomicity, Dundun callback with HMAC + idempotency, RLS isolation, MF-2 bidirectional WS bridge) shipped and in production.

Re-open per-epic items as EP-04 / EP-05 / EP-12 lands their consumer surfaces.
