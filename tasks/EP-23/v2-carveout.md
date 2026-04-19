# EP-23 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Post-MVP Feedback Batch 2: F-1, F-2, F-3-headings, F-4, F-5, F-6, F-7-component all shipped (FE 1670/1670 + BE 1964/1964 green per prior `review-before-push`).

The items below were explicitly deferred in the Status section of `tasks.md` and are re-filed here for formal v2 tracking (same pattern as EP-12/EP-19/EP-20/...):

## F-3 a11y gates (matches EP-12 / EP-19 / EP-20 CI-gate carveout)

- **Sweep pages for discernible names** (`tasks.md` line 47): `items`, `items/[id]`, `teams`, `admin`, `inbox`, `dashboard`. Headings fixed (5 pages + work-item `<h1>` + dashboard `<h1>` + admin h3→h2). Full button/icon/filter-chip/control sweep deferred — rolls into the dedicated a11y epic.
- **Fix missing `aria-label`** on buttons, icon-buttons, filter chips, section headings, form controls (`tasks.md` line 48).
- **Run axe-core — zero "discernible name" violations** (`tasks.md` line 49). Matches the axe-core CI gate carveout in EP-12/EP-19/EP-20.
- **Document sweep findings in `design.md`** (`tasks.md` line 50).

## F-4 duplicate / role-gate polish

- **Remove / demote duplicate "New item" CTA** (`tasks.md` line 55): dashboard + sidebar CTA kept; items-list header retains a scoped secondary CTA. Cosmetic — acceptable for MVP.
- **Respect auth/role hide/disable rules** (`tasks.md` line 56): matches existing Items header button behavior. Add when role-based UI gating lands generically.

## F-6 detail-page layout polish

- **Auto-collapse main sidebar on detail page; restore on exit** (`tasks.md` line 77) — pending page-level wiring. Low priority; users can toggle manually.
- **Status strip full content** (`tasks.md` line 80): LockBadge wired; completeness pill + item-type + assignee deferred (stripe shell exists, panels opt-in).

## F-7 detail-redesign (explicitly v2)

- **Page integration: swap `WorkItemDetailPage` to render `ItemDetailShell`** (`tasks.md` line 87) — breaks ~1800 LoC of pre-existing tests. Treated as a v2 detail-redesign epic; `ItemDetailShell` component ready (21 tests green) when product pulls the trigger.
- **Manual QA: open multiple item types via shell** (`tasks.md` line 88) — depends on page integration.

## Manual QA gates

- **F-1 manual QA** — hit `/workspace/<slug>` while logged out, verify zero flash (`tasks.md` line 33). Middleware + layout guard are unit-tested (10 + 2 tests); manual confirmation is a release QA step.

---

MVP scope (auth/session gate, dashboard lean, F-3 heading fixes, sidebar CTA + zones, inbox full-width, detail-page F-6 shell partial, ItemDetailShell component in isolation) shipped and in production.
