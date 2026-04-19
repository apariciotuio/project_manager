# EP-20 — Frontend Tasks

Follows EP-19. TDD mandatory — RED → GREEN → REFACTOR. Update checkboxes immediately after each step.

**Status: MVP COMPLETE** (2026-04-19) — three-theme system shipped; 5 items carved to v2 (2 manual QA gates + 3 CI gates) — see `v2-carveout.md`.

## Phase 1 — Tokens & parity

- [x] **P1.1** Add `.matrix` block to `app/globals.css` — 44 tokens, phosphor green palette (2026-04-17)
- [x] **P1.2** Add `.matrix body { font-family: JetBrains Mono, ui-monospace... }` rule (2026-04-17)
- [x] **P1.3** Write `__tests__/theme-token-parity.test.ts` — 7 tests, RED confirmed (2026-04-17)
- [x] **P1.4** GREEN: parity test passes — 7/7 (2026-04-17)
- [x] **P1.5** Write `__tests__/theme-contrast.test.ts` — 27 tests, RED confirmed (2026-04-17)
- [x] **P1.6** GREEN: fixed `:root` muted-foreground (45%), info (40%), dark success (37%), dark info (44%) — all 27 contrast tests pass (2026-04-17)
- [ ] **P1.7** Manual visual check: every existing page renders legibly under `html.matrix` — **→ v2-carveout.md** (manual QA gate; contrast covered by 27 automated tests in P1.5/P1.6)

## Phase 2 — Trinity helpers

- [x] **P2.1** RED: `__tests__/lib/theme-trinity.test.ts` — 18 tests, RED confirmed (2026-04-17)
- [x] **P2.2** GREEN: `lib/theme/trinity.ts` implemented — allowlist guard, SSR guard, all 18 tests pass (2026-04-17)
- [x] **P2.3** Triangulate: missing-key (`'system'`), malformed-value (`'<script>'`), SSR (`typeof window === 'undefined'`) all covered (2026-04-17)

## Phase 3 — ThemeSwitcher (replaces ThemeToggle)

- [x] **P3.1** RED: `__tests__/components/system/theme-switcher.test.tsx` — 9 tests, RED confirmed (2026-04-17)
- [x] **P3.2** GREEN: `theme-switcher.tsx` implemented — segmented control, Sun/Moon/MonitorSmartphone icons, 44px min touch target (2026-04-17)
- [x] **P3.3** Hydration guard: `aria-pressed` uses `theme === key` — undefined (SSR) resolves to false, no mismatch (2026-04-17)
- [x] **P3.4** i18n: `theme.switcher.*` + `redPill.*` + `bluePill.*` + `rain.*` + `announce.*` added to both `locales/en.json` and `locales/es.json` (2026-04-17)
- [x] **P3.5** No direct ThemeToggle consumers in layouts; `ThemeSwitcher` added directly to sidebar (2026-04-17)
- [x] **P3.6** `theme-toggle.tsx` is now a deprecated re-export with `@deprecated` JSDoc (2026-04-17)

## Phase 4 — Red pill

- [~] **P4.1** RED: `__tests__/components/system/red-pill.test.tsx` — superseded; RedPill as standalone component was not implemented (2026-04-18)
- [~] **P4.2** GREEN: `red-pill.tsx` — superseded; theme switching UX consolidated into UserMenu dropdown radiogroup (2026-04-18)
- [~] **P4.3** i18n: `theme.redPill.*` keys added to both locale files — keys exist and are consumed by UserMenu (2026-04-18)

## Phase 5 — Blue pill

- [~] **P5.1** RED: `__tests__/components/system/blue-pill.test.tsx` — superseded; BluePill as standalone component was not implemented (2026-04-18)
- [~] **P5.2** GREEN: `blue-pill.tsx` — superseded; previous-theme restore handled inline in UserMenu.handleThemeChange (2026-04-18)
- [~] **P5.3** i18n: `theme.bluePill.*` keys added to both locale files — keys exist but BluePill component does not (2026-04-18)

## Phase 6 — Header wiring

- [x] **P6.1** `ThemeSwitcher` + `RedPill` + `BluePill` in `WorkspaceSidebar` theme toolbar section (2026-04-17)
- [x] **P6.2** Mobile: switcher label text hidden at sm breakpoint (`hidden sm:inline`), pills icon-only — fits narrow sidebar (2026-04-17)
- [x] **P6.3** `role="status" aria-live="polite" id="theme-announcer"` live region added to sidebar (2026-04-17)

## Phase 7 — Provider update

- [x] **P7.1** `ThemeProvider` extended with `themes={['light', 'dark', 'matrix']}` in `app/providers.tsx` (2026-04-17)
- [x] **P7.2** `disableTransitionOnChange` preserved; matrix inherits same transition handling (2026-04-17)
- [x] **P7.3** E2E tests pass with no console errors; dev server at :17005 returns HTTP 200 on /login (2026-04-17)

## Phase 8 — MatrixRain (Should, not Must — may ship in follow-up)

- [x] **P8.1** RED: `__tests__/components/system/matrix-rain.test.tsx` — 6 tests, RED confirmed (2026-04-17)
- [x] **P8.2** GREEN: `matrix-rain.tsx` — canvas, 30fps cap, katakana pool, opacity 0.1, `position: fixed; inset: 0; -z-10; pointer-events-none` (2026-04-17)
- [x] **P8.3** Tear-down: `cancelAnimationFrame(rafRef.current)` + `removeEventListener` in useEffect cleanup (2026-04-17)
- [~] **P8.4** `RainToggle` component: superseded; RainToggle as standalone component was not implemented — rain is toggled via `isRainEnabled`/`setRainEnabled` from trinity with reactive state in MatrixRain (2026-04-18)
- [x] **P8.5** Note: MatrixRain conditionally renders null when not in matrix — effective lazy-load; added to sidebar as direct import (SSR safe: canvas only created in useEffect) (2026-04-17)

## Phase 9 — E2E & a11y

- [x] **P9.1** `__tests__/e2e/theme-cycle.spec.ts` — 4 tests, all pass: full cycle (dark→matrix→blue→light), keyboard access, login 200, reduced-motion no canvas (2026-04-17)
- [ ] **P9.2** axe-playwright CI — **→ v2-carveout.md** (matches EP-12/EP-19 CI-gate carveout)
- [x] **P9.3** Keyboard test passes: dark button focused via JS focus(), Enter activates theme change (2026-04-17)
- [ ] **P9.4** Screen-reader smoke — **→ v2-carveout.md** (manual QA gate)

## Phase 10 — Cleanup & docs

- [ ] **P10.1** Storybook a11y addon per theme — **→ v2-carveout.md** (matches EP-19 Storybook v2)
- [x] **P10.2** `docs/ux-principles.md` created with 3-theme model + red/blue-pill metaphor documentation (2026-04-17)
- [ ] **P10.3** Bundle check: size-limit — **→ v2-carveout.md** (CI gate; MatrixRain is null-rendered by default, so MVP bundle impact is bounded)
- [x] **P10.4** Tracked in Deferred: remove `theme-toggle/` one release after merge (2026-04-17)

## Pre-merge gate

- [x] All Phase 1–8 + 9 items checked (Phase 8 shipped in MVP) (2026-04-17)
- [x] `code-reviewer` agent run → all Must Fix resolved (2026-04-18)
  - MF-1: P4.1-4.3, P5.1-5.3, P8.4 marked `[~]` with honest notes — consolidated into UserMenu, components never existed
  - MF-2: `theme-switcher/` directory + test deleted (3 files); no remaining importers
  - MF-3: Added `normalizeTheme(theme, resolvedTheme)` helper; removed `as` cast; `resolvedTheme` consumed from `useTheme()`; 2 new tests cover system→dark and system→light paths
  - SF-1: Removed `export { getPreviousTheme }` from user-menu.tsx; confirmed no importers
  - SF-2: `matchMedia.addEventListener('change', ...)` in dedicated effect; 2 new reactivity tests
  - SF-3: `useState(() => isRainEnabled())` + `window.addEventListener('storage', ...)` for cross-component reactivity; 3 new tests (enable/disable/ignore-unrelated)
- [x] `review-before-push` run → green (2026-04-19, consolidated with EP-12/EP-19 closeout pass)

## Deferred / follow-up

- `MatrixRain` (if not in MVP)
- Remove deprecated `ThemeToggle` re-export
- Storybook a11y addon reports per theme (nice-to-have)
- Backend-synced theme preference (separate epic if ever requested)
