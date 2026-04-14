# EP-19 — Design System & Frontend Foundations · Task Tracker

## Status

| Phase | Status |
|---|---|
| Proposal | **COMPLETED** (2026-04-14) |
| Specs (4 capabilities) | **COMPLETED** (2026-04-14) |
| Design | **COMPLETED** (2026-04-14) |
| Division approved | **COMPLETED** (2026-04-14) — frontend-only |
| Frontend plan (`plan-frontend.md`) | **COMPLETED** (2026-04-14) |
| Backend plan | **N/A** (frontend-only) |
| Retrofit table in `tasks/extensions.md#EP-19` | **COMPLETED** (2026-04-14) — 18 epics covered; EP-12 exempt |
| "Follows EP-19" preambles in each epic's `tasks-frontend.md` | **COMPLETED** (2026-04-14) — EP-00..EP-18 + reciprocal note in EP-12 |
| Cross-epic consistency review (round 2) | **COMPLETED** (2026-04-14) — `tasks/consistency_review_round2.md` |
| Specialist reviews (arch + sec + front + a11y) | **COMPLETED** (2026-04-14) — `tasks/reviews/round_2_specialist_reviews_summary.md` + 4 per-reviewer docs; 24 Must-fix applied as addendum blocks in affected specs; Should-fix + Nitpick backlogged |
| Implementation — Phase A (foundation) | PENDING |
| Implementation — Phase B (catalog) | PENDING |
| Migration wave (EP-00..EP-18 retrofit) | PENDING |

## Capabilities

| # | Capability | Spec |
|---|---|---|
| 1 | Design Tokens & Theming | [specs/tokens-and-theming/spec.md](specs/tokens-and-theming/spec.md) |
| 2 | Shared Domain Components | [specs/shared-components/spec.md](specs/shared-components/spec.md) |
| 3 | Copy, Tone, i18n Base | [specs/copy-tone-i18n/spec.md](specs/copy-tone-i18n/spec.md) |
| 4 | Accessibility & Performance Gates | [specs/a11y-and-performance/spec.md](specs/a11y-and-performance/spec.md) |

## Critical Path

```
Phase A (foundation) ──> Phase B (catalog) ──> Phase C (migration wave)
                                                    │
                                                    ├─> EP-18 retrofit
                                                    ├─> EP-17 retrofit
                                                    ├─> EP-09 retrofit
                                                    └─> ... (rolling)
```

## Dependencies

| Dep | Usage |
|---|---|
| EP-12 | Layout primitives (AppShell, BottomSheet, DataTable, EmptyState, SkeletonLoader, ErrorBoundary). EP-19 extends, does not replace. |

## Blocks / enables

EP-19 is **unblocking** for every frontend epic that starts **after** it. Epics already mid-plan (EP-00..EP-18) retrofit via `extensions.md` entries.

## Non-Goals (reminder)

- No business features
- No backend work
- No replacement of EP-12 primitives
- No feature-specific components

## Artifacts

- `proposal.md`
- `design.md`
- `specs/<capability>/spec.md` × 4
- `plan-frontend.md` (to create)
- Retrofit entries in `tasks/extensions.md`

## Open Questions

1. Brand accent color — slot defined; design fills later
2. Visual regression (Chromatic) — deferred
3. next-intl vs custom — custom for MVP
