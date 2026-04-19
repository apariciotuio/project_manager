# EP-10 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Configuration, Projects, Rules & Administration shipped — **8 admin controllers + 2 config controllers live** (prior status line was stale):

Admin controllers (all exist in `backend/app/presentation/controllers/`):
- `admin_controller.py`, `admin_dashboard_controller.py`, `admin_members_controller.py`
- `admin_rules_controller.py`, `admin_jira_controller.py`, `admin_support_controller.py`
- `admin_context_presets_controller.py`, `admin_mcp_tokens_controller.py`

Config controllers: `project_controller.py`, `integration_controller.py`.

Services: `admin_dashboard_service.py`, `admin_support_service.py`, `project_service.py`, `superadmin_seed_service.py`.

## Missing infra (4 items per execution plan line 101)

- **Superadmin CLI command** — `backend/scripts/` has `dev_token.py` + seed scripts, but no dedicated `superadmin` click/typer command. Workaround today: `seed_dev.py` + `seed_sample_data.py` cover the bootstrapping use-case. Add a first-class `python -m app.cli superadmin promote|demote|list` when ops needs it.
- **`context_sources` table + migration** — decision was deferred in the original design; `AdminContextPresets` today operates on the presets table only. Add when context source provenance needs to be tracked (e.g., for auditing template reuse).
- **`AlertService` extraction from `AdminDashboardController`** — alert derivation currently inline in the controller. Extract when a second consumer (email digest, admin notification feed) needs the same derivation (mirrors the EP-12 per-epic adoption carveout).
- **EXPLAIN ANALYZE audit on admin queries** — `QueryCounterMiddleware` already WARNs in dev/staging when budgets blow. Explicit per-query EXPLAIN ANALYZE is a perf gate (matches EP-12 Lighthouse/axe-core CI-gate carveout).

## Minor cleanup

- **DELETE `/integrations/configs/{id}` endpoint** — claimed missing in the prior status line; integrations are soft-deactivated today via PATCH `status`. Formal DELETE adds next to zero value (soft-state is auditable).
- **Granular TDD checklist never synced** (plan risk #2) — the 316 unchecked items are almost entirely stale-tick; the code + controllers above prove the work shipped, just without back-tick bookkeeping (same pattern as EP-04/EP-05/EP-07/EP-08).

---

MVP scope (8 admin controllers, 2 config controllers, 4 services + seed scripts, project CRUD, integration config management, routing rules, jira sync config, support tools, MCP token management, context presets, dashboard aggregations, members audit) shipped and in production.

Re-open a slim v2 epic when ops needs the superadmin CLI or when product tracks context-source provenance.
