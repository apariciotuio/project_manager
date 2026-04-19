# EP-03 Phase 8 — Security review findings (2026-04-16)

Review run by `code-reviewer` subagent over the EP-03 Phase 7 controllers, adapters and migrations.

Scope:
- `backend/app/presentation/controllers/conversation_controller.py` (threads + WS proxy)
- `backend/app/presentation/controllers/suggestion_controller.py`
- `backend/app/presentation/controllers/clarification_controller.py`
- `backend/app/presentation/controllers/dundun_callback_controller.py`
- `backend/app/infrastructure/adapters/dundun_http_client.py`
- `backend/app/infrastructure/adapters/dundun_callback_verifier.py`
- Repository impls for the 3 new tables
- Migrations 0014/0015/0016

## Summary

| Severity | Title | Status |
|---|---|---|
| Must Fix | 1. Missing workspace RLS on `conversation_threads`, `assistant_suggestions`, `gap_findings` | Deferred — needs migration 0017 |
| Must Fix | 2. WS proxy bidirectional broken (upstream `send` no-op via `asend()` on async generator) | Deferred — needs `DundunClient.chat_ws` refactor |
| Must Fix | 3. Suggestion controller IDOR (consequence of #1) | Deferred with #1 |
| Must Fix | 4. Clarification service correctly scoped via `workspace_id` | ✅ Confirmed OK, no change needed |
| Must Fix | 5. Callback generates random UUIDs on missing `work_item_id`/`user_id` → FK failure → Dundun retries forever | ✅ Fixed — now returns 422 |
| Should Fix | 6. Callback lacks outstanding-request binding (trusts Dundun's `request_id`) | Deferred |
| Should Fix | 7. JWT leaks to access logs via `?token=` query param | Deferred to EP-12 |
| Should Fix | 8. `JwtAdapter` constructed per WS connection | Deferred — minor perf |
| Should Fix | 9. `service._thread_repo` / `service._suggestion_repo` accessed from controllers | Deferred — refactor into service API |
| Nitpick | 10. `dependencies.py:282` comment typo (`app.current_workspace_id` vs `app.current_workspace`) | Nit |
| Nitpick | 11. `async for thread_repo in get_thread_repo_for_ws():` is a single-iter loop | Works correctly, leave |
| Nitpick | 12. Gap callback does `get_active_for_work_item` then Python-side filter for `dundun_request_id` | Optimize when data grows |
| ✅ | 13. No LLM SDK leakage, no prompt YAMLs | Confirmed clean |

## Deferred Must-Fix details

### Must Fix #1 — workspace RLS on the 3 new tables

`migrations/versions/0009_create_work_items.py` uses `workspace_id` + `ALTER TABLE work_items ENABLE ROW LEVEL SECURITY` + `CREATE POLICY ... USING (workspace_id::text = current_setting('app.current_workspace', true))`. That pattern is NOT applied to 0014/0015/0016. Within a workspace, any authenticated user can:

- `POST /api/v1/work-items/{wi_id}/suggestion-sets` with a work_item_id belonging to any workspace (UUID guessing)
- `GET /api/v1/suggestion-sets/{batch_id}` for any batch
- `PATCH /api/v1/suggestion-items/{item_id}` for any item
- `GET /api/v1/work-items/{wi_id}/gaps/questions` → goes through ClarificationService which DOES check workspace_id (this path is safe)

Within-workspace IDOR is the real risk, but UUID guessing on a closed VPN with <100 users makes exploitation impractical. Still the house pattern must hold.

**Fix plan** (ticket-ready):
1. Migration `0017_rls_for_ep03_tables.py`
   - `ALTER TABLE conversation_threads ADD COLUMN workspace_id UUID REFERENCES workspaces(id)` (NULL allowed for general threads — or always require it)
   - `ALTER TABLE assistant_suggestions ADD COLUMN workspace_id UUID NOT NULL REFERENCES workspaces(id)`
   - `ALTER TABLE gap_findings ADD COLUMN workspace_id UUID NOT NULL REFERENCES workspaces(id)`
   - Backfill from `work_items.workspace_id` for existing rows (empty in dev/test)
   - Enable RLS + create `*_workspace_isolation` policies
2. Update ORM models + mappers
3. Update repositories to accept `workspace_id` on insert
4. Services derive `workspace_id` from work_item (or from current_user) and pass to repo
5. Callback controller: look up `work_item.workspace_id` and set on insert
6. Two-tenant integration test for each of the 3 tables confirming isolation

Estimated ~2-3 h.

### Must Fix #2 — WS proxy bidirectional broken

`DundunHTTPClient.chat_ws` is a plain async generator that yields upstream frames. The controller's `_UpstreamWS.send(frame)` calls `self._gen.asend(frame)` — on a generator that never `yield value = <value received from send>`, `asend()` is equivalent to `__anext__()` and the sent value is discarded.

Current behavior: upstream→client frames work; client→upstream frames are silently dropped. Visible at runtime only when users try to type a prompt through the proxy.

**Fix plan**:
- Refactor `DundunClient.chat_ws(...)` to return an `async with` context that wraps the underlying `websockets` connection, exposing `.send()` and `.recv()` directly.
- Update `_UpstreamWS` to use those methods instead of generator protocol.
- Add E2E test with a stub Dundun WS server that echoes.

### Must Fix #3 — consequence of #1

Covered by the fix for #1.

## Resolved in this pass

### #5 — Callback FK validation

`_handle_suggestion` and `_handle_gap` in `dundun_callback_controller.py` now return HTTP 422 with code `MISSING_IDS` when required UUIDs are missing from the payload, instead of generating a random UUID that would fail the FK constraint on insert and trigger an infinite retry loop on Dundun's side.

Test coverage: existing 8 integration tests still pass. New negative tests should be added when RLS work (#1) lands — the callback surface is changing anyway.

## Tests after this pass

- `pytest tests/` → **892 passed, 1 skipped** (WS bidirectional test skips itself, see #2).
- `ruff check` on new/changed files → clean.
- `mypy --strict` on EP-03 Phase 7 files → zero errors (pre-existing debt in other files unchanged).

## Decisions log entry

If the user decides to ship EP-03 without fixing #1 / #2 / #3 before moving on to EP-04, an entry in `decisions.log.md` will record that the known gaps are accepted for the current VPN-internal deployment and must be closed before any external exposure.
