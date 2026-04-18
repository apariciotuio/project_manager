# EP-19 · Frontend Tasks

Frontend-only epic. Executed in three phases: **A — Foundation**, **B — Catalog**, **C — Migration**. TDD where feasible (token tests, component tests, hook tests, lint-rule tests). Storybook stories authored alongside components.

## Phase A — Foundation
**Status: COMPLETED** (2026-04-16)

### A.1 shadcn + Tailwind + Inter

- [x] Created `components.json` with RSC + Tailwind paths (2026-04-16)
- [x] Expanded `tailwind.config.ts` with full semantic color tokens mapped to CSS variables (2026-04-16)
- [x] Expanded `frontend/app/globals.css` with CSS variables for light AND dark for every semantic token (parity CI test) (2026-04-16)
- [x] Installed Inter via `next/font/google` in `frontend/app/layout.tsx`; defined semantic text classes `text-display`, `text-h1`..`text-caption`, `text-code` in `@layer utilities` (2026-04-16)
- [x] Installed `lucide-react` as the only icon library (2026-04-16)
- [x] `next-themes` ThemeProvider wired in `app/providers.tsx`; `<ThemeToggle>` refactored to `components/system/theme-toggle/` with lucide icons; `useTheme` hook wraps next-themes (2026-04-16)
- [x] `size-limit` config at `frontend/size-limit.config.js`; per-route limit 200 KB gzipped (2026-04-16)

### A.2 Initial shadcn component install

- [x] Manually installed shadcn-style components: button, badge, input, label, separator, skeleton, avatar, progress, card, dialog, tabs, tooltip, checkbox, switch, scroll-area, popover, command, textarea (2026-04-16)
- [x] All components reference semantic tokens (no raw colors) (2026-04-16)
- [x] Storybook 8 scaffolding (`frontend/.storybook/main.ts` + `preview.ts`), `addon-a11y`, `addon-docs` enabled (2026-04-16)

### A.3 Lint rules

- [x] Implemented `no-raw-tailwind-color` (`frontend/eslint-rules/no-raw-tailwind-color.js`) (2026-04-16)
- [x] Implemented `no-raw-text-size` (`frontend/eslint-rules/no-raw-text-size.js`) (2026-04-16)
- [x] Implemented `no-literal-user-strings` (`frontend/eslint-rules/no-literal-user-strings.js`) (2026-04-16)
- [x] Implemented `tone-jargon` with `tone-jargon.json` wordlist (`frontend/eslint-rules/tone-jargon.js`) (2026-04-16)
- [x] All four rules wired in `frontend/.eslintrc.json` via `eslint-plugin-local-rules`; `frontend/eslint-local-rules.js` is the entry point (2026-04-16)
- [x] Rule tests under `frontend/eslint-rules/__tests__/` — all 4 pass via `node` + integrated into vitest via wrapper (2026-04-16)

### A.4 i18n base

- [x] Created `frontend/lib/i18n/es/` with seeded dictionaries: common, errors, workitem, review, hierarchy, tags, attachment, lock, mcp, assistant, role (2026-04-16)
- [x] Created `frontend/lib/i18n/en/` as stub mirror (2026-04-16)
- [x] Implemented typed `t()` getter + `icuLite` (plural/select) in `frontend/lib/i18n/index.ts` (2026-04-16)
- [x] Existing `next-intl` wiring kept in `app/layout.tsx` + `app/providers.tsx` for backward compat (2026-04-16)
- [x] 14 tests for `t()` getter, `icuLite`, and dict structure — all passing (2026-04-16)

## Phase B — Shared domain catalog
**Status: COMPLETED** (2026-04-16)

For each component the pattern is: **RED** tests → **GREEN** component → **REFACTOR** → component test.

### B.1 State & identity badges

- [x] `StateBadge` — role=status, aria-label, all 6 states, size prop (2026-04-16)
- [x] `TypeBadge` — all 9 types, role=img (2026-04-16)
- [x] `LevelBadge` — low/medium/high/ready with level semantic tokens (2026-04-16)
- [x] `SeverityBadge` — blocking/warning/info with severity semantic tokens (2026-04-16)
- [x] `TierBadge` — inbox 1..4 with tier semantic tokens (2026-04-16)
- [x] `JiraBadge`, `LockBadge`, `VersionChip`, `RollupBadge` (2026-04-16)

### B.2 Tags & people

- [x] `TagChip` with luminance-based contrast text (lib/color.ts — hexToRgb, relativeLuminance, contrastRatio, pickContrastColor with cache) (2026-04-16)
- [x] `TagChipList` with `+N` overflow (2026-04-16)
- [x] `OwnerAvatar`, `UserAvatar` (Radix Avatar, initials fallback, accessible aria-label) (2026-04-16)

### B.3 Progress

- [x] `CompletenessBar` (aria-valuenow/min/max, level color tokens, percent clamping) (2026-04-16)

### B.4 Confirmations

- [x] `TypedConfirmDialog` (typed-name match gate, async onConfirm, close on cancel) (2026-04-16)
- [x] `CheckboxConfirmDialog` ("Entiendo que no se puede deshacer" pattern) (2026-04-16)

### B.5 Critical UX moments

- [x] `PlaintextReveal` — auto-clear timer, no localStorage/sessionStorage writes (security tested), hide button, copy button (2026-04-16)
- [x] `CopyButton` — clipboard API, confirmation flash "Copiado", keyboard accessible (2026-04-16)

### B.6 Navigation & shortcuts

- [x] Hook `useKeyboardShortcut(combo, handler, options?)` — modifier matching, form-field suppression, cleanup on unmount (2026-04-16)
- [ ] `CommandPalette` — `⌘K` / `Ctrl+K`, fuzzy search, recents, registry — DEFERRED to follow-up (infrastructure from B.6 hook + shadcn Command ready)
- [ ] `ShortcutCheatSheet` — `?` key — DEFERRED to follow-up

### B.7 Content

- [x] `HumanError` (code → ES message, generic fallback, console.warn for unmapped, role=alert, text nodes only) (2026-04-16)
- [x] `RelativeTime` (wraps `<time datetime>`, 1 Hz update, `useRelativeTime` hook) (2026-04-16)
- [ ] `DiffHunk` — DEFERRED (no consumer in EP-00..current migration scope)
- [ ] `EmptyStateWithCTA` — DEFERRED (EP-12 EmptyState not yet available)

### B.8 Hooks

- [x] `useAutoClearPlaintext(ms)` — fake-timer tests (2026-04-16)
- [x] `useCopyToClipboard()` — happy + error paths (2026-04-16)
- [x] `useRelativeTime(iso)` — 1 Hz re-render, matchMedia mock (2026-04-16)
- [x] `useKeyboardShortcut` — modifier matching + cleanup (2026-04-16)
- [x] `useTheme()` — wraps next-themes (2026-04-16)
- [x] `useHumanError(code)` — resolves + marks unmapped with console.warn (2026-04-16)
- [ ] `useCommandPalette()` — DEFERRED with CommandPalette

## Phase C — Migration (per-epic retrofit)
**Status: COMPLETED for EP-00** (2026-04-16)

- [x] EP-00 — login/workspace-picker cosmetic pass (2026-04-16)
  - `frontend/app/login/page.tsx`: gray/red/blue → semantic tokens; text-2xl → text-h1; Skeleton loading; Button + AlertCircle
  - `frontend/app/workspace/select/page.tsx`: all raw colors → semantic tokens; text-xl → text-h2; Skeleton loading; Button+Separator list
  - `frontend/app/workspace/[slug]/page.tsx`: inline initials → UserAvatar; all raw colors → semantic; text-sm → text-body-sm
  - `frontend/components/auth/logout-button.tsx`: raw button → Button variant=ghost + LogOut icon
- [ ] EP-01 through EP-18 migrations — out of scope for this session (no frontend code yet for those epics)

## Quality gates (always on)

- [x] Dark mode parity test — 4 tests passing (2026-04-16)
- [x] ESLint rules fire on violations (verified on login page pre-migration) (2026-04-16)
- [x] All 171 unit tests pass (2026-04-16)
- [x] TypeScript strict — clean (2026-04-16)
- [ ] Lighthouse a11y ≥ 95 — requires deployed environment (CI gate)
- [ ] axe-playwright on E2E — requires Playwright run (CI gate)
- [ ] `size-limit` per route — requires `next build` (CI gate)
- [ ] Storybook builds without errors — install complete, build not yet run

## Storybook coverage

Stories deferred — Storybook scaffold exists (`frontend/.storybook/`), stories to be authored in follow-up session.

## Effort estimate

| Phase | Status |
|---|---|
| A — Foundation | COMPLETED 2026-04-16 |
| B — Catalog (25 components + hooks) | COMPLETED core (2026-04-16); CommandPalette/ShortcutCheatSheet/DiffHunk/EmptyStateWithCTA deferred |
| C — Migration | EP-00 COMPLETED (2026-04-16); EP-01..EP-18 deferred (no frontend code yet) |
