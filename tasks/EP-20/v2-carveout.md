# EP-20 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** Three-theme system (light / dark / matrix) with trinity helpers, ThemeSwitcher, Red/Blue pills (consolidated into UserMenu), and MatrixRain canvas shipped. Parity + contrast covered by 34 automated tests.

## Manual QA gates

- **P1.7 — Matrix visual smoke across every page** (`tasks-frontend.md` line 13): automated contrast is enforced by the 27 tests in `__tests__/theme-contrast.test.ts` + the 7-test parity suite; a human click-through per page is a QA responsibility, not a dev deliverable.
- **P9.4 — Screen-reader smoke** (`tasks-frontend.md` line 67): manual pass; keyboard nav + `aria-pressed` covered by `__tests__/e2e/theme-cycle.spec.ts`.

## CI gates (v2 CI epic — matches EP-12 / EP-19)

- **P9.2 — axe-playwright CI gate** (`tasks-frontend.md` line 65): requires Playwright CI run.
- **P10.1 — Storybook a11y addon per theme** (`tasks-frontend.md` line 71): scaffold exists; per-theme story authoring deferred.
- **P10.3 — `size-limit` bundle check** (`tasks-frontend.md` line 73): MatrixRain renders `null` unless `html.matrix`, so MVP bundle impact is bounded; proper budget requires CI `next build`.

---

MVP scope (token parity, contrast, trinity helpers, ThemeSwitcher, MatrixRain with reactive toggle, cycle E2E, provider wiring, i18n EN + ES, docs) shipped and in production.

Re-open under the v2 CI epic when we're ready to gate builds on a11y/bundle-size.
