# EP-20 — Theme System: Light / Dark / Matrix

Frontend-only. Extends EP-19 (Design System).

## Artifacts

- [x] `proposal.md` — business need, objectives, stories, AC
- [x] `design.md` — decisions, components, token diff, flows, security approach
- [x] `specs/theme-matrix/spec.md` — WHEN/THEN scenarios + Threat→Mitigation table
- [x] `plan-frontend.md` — detailed implementation plan (10 phases, file map, test boundaries)
- [x] `tasks-frontend.md` — implementation checklist (10 phases)
- [ ] Implementation

## Progress

| Phase | Status |
|-------|--------|
| Proposal / Specs / Design / Tasks | **COMPLETED** (2026-04-17) |
| Phase 1 — Tokens & parity | **COMPLETED** (2026-04-17) |
| Phase 2 — Trinity helpers | **COMPLETED** (2026-04-17) |
| Phase 3 — ThemeSwitcher | **COMPLETED** (2026-04-17) |
| Phase 4 — Red pill | **COMPLETED** (2026-04-17) |
| Phase 5 — Blue pill | **COMPLETED** (2026-04-17) |
| Phase 6 — Header wiring | **COMPLETED** (2026-04-17) |
| Phase 7 — Provider update | **COMPLETED** (2026-04-17) |
| Phase 8 — MatrixRain | **COMPLETED** (2026-04-17) |
| Phase 9 — E2E & a11y | **COMPLETED** (2026-04-17) — 4 new E2E tests pass; axe-playwright deferred |
| Phase 10 — Cleanup & docs | **COMPLETED** (2026-04-17) — Storybook addon deferred |
| Frontend implementation | **COMPLETED** (2026-04-17) |
| code-review | **COMPLETED** (2026-04-18) — 3 MF (dead code ThemeSwitcher, pill/rain components not implemented vs plan, unsafe cast) + 3 SF (re-export, MatrixRain reduced-motion listener, rainEnabled reactivity) + 3 Nitpick; all MF+SF resolved by fix agent |
| review-before-push | Not started (user requested no push yet) |

## Dependencies

- **EP-19** — design tokens, `ThemeProvider` wiring, Storybook, axe-core pipeline (hard dependency, already ✅ Done)

## Key references

- Existing `ThemeToggle`: `frontend/components/system/theme-toggle/theme-toggle.tsx` (to be replaced by `ThemeSwitcher`)
- Existing tokens: `frontend/app/globals.css` (add `.matrix` block)
- Provider: `frontend/app/providers.tsx` (extend `themes` array)

## Open questions captured in proposal

1. Ship `MatrixRain` in MVP or defer? → **Defer** (Should)
2. Pill placement? → **Header toolbar** next to `ThemeSwitcher`
3. Keyboard shortcut? → **No** in MVP
4. Wire Trinity endpoint here? → **No** — reserve `trinity.ts` naming only
