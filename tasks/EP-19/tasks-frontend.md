# EP-19 · Frontend Tasks

Frontend-only epic. Executed in three phases: **A — Foundation**, **B — Catalog**, **C — Migration**. TDD where feasible (token tests, component tests, hook tests, lint-rule tests). Storybook stories authored alongside components.

## Phase A — Foundation

### A.1 shadcn + Tailwind + Inter

- [ ] Run `pnpm dlx shadcn@latest init`; commit `components.json` with RSC + Tailwind paths
- [ ] Edit `tailwind.config.ts` — add semantic color tokens (mirror of `globals.css`)
- [ ] Edit `apps/web/src/styles/globals.css` — CSS variables for light AND dark for every semantic token (parity CI test)
- [ ] Install Inter via `next/font/google` in `apps/web/src/app/layout.tsx`; define semantic text classes (`text-display`, `text-h1`, `text-h2`, `text-body`, `text-caption`, `text-code`)
- [ ] Install `lucide-react` as the only icon library; forbid others in lint
- [ ] `next-themes` wiring for dark mode + SSR cookie; `<ThemeToggle>` under `components/system/theme-toggle/`
- [ ] `size-limit` config `apps/web/size-limit.config.js`; per-route limit 200 KB gzipped

### A.2 Initial shadcn component install

- [ ] `pnpm dlx shadcn@latest add button dialog alert-dialog dropdown-menu input label select textarea toast table badge tabs sheet tooltip separator skeleton card command popover scroll-area avatar checkbox radio-group switch progress combobox`
- [ ] Verify each installed component references semantic tokens (no raw colors)
- [ ] Storybook 8 scaffolding (`apps/web/.storybook/`), `addon-a11y`, `addon-docs` enabled

### A.3 Lint rules

- [ ] Implement `no-raw-tailwind-color` (ESLint custom rule under `apps/web/eslint-rules/`)
- [ ] Implement `no-raw-text-size`
- [ ] Implement `no-literal-user-strings`
- [ ] Implement `tone-jargon` with `tone-jargon.json` wordlist (submit, click here, Are you sure, Ready, Draft, token, usted, …)
- [ ] Add all four rules to `apps/web/.eslintrc`; configure safelists

### A.4 i18n base

- [ ] Create `apps/web/src/i18n/es/*.ts` with seeded dictionaries (common, errors, workitem, review, hierarchy, tags, attachment, lock, mcp, assistant, role)
- [ ] Create `apps/web/src/i18n/en/` as stub mirror
- [ ] Implement typed `t()` getter + `icuLite` (plural/select)
- [ ] `I18nProvider` in `app/layout.tsx`
- [ ] `useLocale()` hook + cookie persistence

## Phase B — Shared domain catalog

For each component the pattern is: **RED** tests → **GREEN** component → **REFACTOR** → Storybook story + docs → axe check.

### B.1 State & identity badges

- [ ] `StateBadge` — [S:shared-components#StateBadge]
- [ ] `TypeBadge`
- [ ] `LevelBadge` (low/medium/high/ready)
- [ ] `SeverityBadge` (blocking/warning/info)
- [ ] `TierBadge` (inbox 1..4)
- [ ] `JiraBadge`, `LockBadge`, `VersionChip`, `RollupBadge`

### B.2 Tags & people

- [ ] `TagChip` with luminance-based contrast text (cache computations)
- [ ] `TagChipList` with `+N` overflow
- [ ] `OwnerAvatar`, `UserAvatar` (initials fallback)

### B.3 Progress

- [ ] `CompletenessBar` (aria-valuenow, level colors)

### B.4 Confirmations

- [ ] `TypedConfirmDialog` (typed-name match gate)
- [ ] `CheckboxConfirmDialog` ("Entiendo que no se puede deshacer")

### B.5 Critical UX moments

- [ ] `PlaintextReveal` — [S:shared-components#PlaintextReveal] — includes 3s gate, interaction gate, autoClearMs, purge-on-close, no-persistence integration test
- [ ] `CopyButton` — clipboard API, confirmation flash, keyboard accessible

### B.6 Navigation & shortcuts

- [ ] `CommandPalette` — `⌘K` / `Ctrl+K`, fuzzy search, recents, registry via `useCommandPaletteRegistry`
- [ ] `ShortcutCheatSheet` — `?` key; per-page registry via `useKeyboardShortcut`; form-field suppression
- [ ] Hook `useKeyboardShortcut(combo, handler, options?)`

### B.7 Content

- [ ] `DiffHunk` (added/removed/context)
- [ ] `HumanError` (code → localized + disclosure)
- [ ] `RelativeTime` (wraps absolute `<time datetime>`)
- [ ] `EmptyStateWithCTA` (wraps EP-12 `EmptyState`)

### B.8 Hooks

- [ ] `useAutoClearPlaintext(ms)` — fake-timer tests
- [ ] `useCopyToClipboard()` — happy + fallback + unsecure context
- [ ] `useRelativeTime(iso)` — 1 Hz re-render, respects reduced-motion
- [ ] `useCommandPalette()` — registry + open/close + scope
- [ ] `useTheme()` (wraps next-themes)
- [ ] `useHumanError(code)` — resolves + marks unmapped

## Phase C — Migration (per-epic retrofit)

Order (smallest surface first):

1. [ ] EP-18 — mcp-tokens screens adopt `PlaintextReveal`, `TypedConfirmDialog`, `StateBadge`, `CopyButton`; drops local copy of each
2. [ ] EP-17 — `LockBadge` adopted; lock banners use `SeverityBadge`
3. [ ] EP-15 — `TagChip`/`TagChipList` adopted
4. [ ] EP-16 — attachments UI adopts `EmptyStateWithCTA`, `TypedConfirmDialog` for delete
5. [ ] EP-14 — hierarchy UI adopts `RollupBadge`, `TypeBadge`
6. [ ] EP-13 — search UI adopts `CommandPalette` for the top-bar search; `HumanError` for Puppet outage
7. [ ] EP-11 — export UI adopts `JiraBadge`, `HumanError`, `TypedConfirmDialog`
8. [ ] EP-10 — admin UI adopts `TypedConfirmDialog`, `StateBadge`, `HumanError`
9. [ ] EP-09 — lists, kanban, dashboards adopt badges uniformly
10. [ ] EP-08 — inbox adopts `TierBadge`; notifications adopt `SeverityBadge`
11. [ ] EP-07 — comments/versions adopt `DiffHunk`, `VersionChip`, `RelativeTime`
12. [ ] EP-06 — reviews adopt `TypedConfirmDialog` (override), `StateBadge`
13. [ ] EP-04 — spec adopts `CompletenessBar`, `LevelBadge`
14. [ ] EP-05 — breakdown adopts `StateBadge` per task
15. [ ] EP-03 — assistant UI adopts `HumanError`, `CopyButton`
16. [ ] EP-02 — capture form adopts `TypeBadge`
17. [ ] EP-01 — state transitions adopt `StateBadge` + `TypedConfirmDialog` (override-ready)
18. [ ] EP-00 — login/workspace-picker cosmetic pass

Each retrofit PR:
- Deletes the local component
- Replaces imports with EP-19 catalog
- Updates tests (component-level tests move to EP-19; epic retains integration-level only)
- Updates i18n strings to use shared dictionary
- Passes a11y + size-limit CI

## Quality gates (always on)

- Lighthouse a11y ≥ 95 per canonical page (blocking check)
- axe-playwright on every E2E (serious+ blocks)
- `size-limit` per route (blocking check)
- Storybook builds and deploys on PR preview
- All ESLint rules (no-raw-color, no-raw-text-size, no-literal-user-strings, tone-jargon) pass

## Storybook coverage

Every component in Phase B ships with:
- Variants story (all states, sizes)
- Interactive controls
- A11y notes in docs tab
- Dark-mode variant

## Effort estimate

| Phase | Estimate |
|---|---|
| A — Foundation | 4 days |
| B — Catalog (25 components + hooks) | 8 days |
| C — Migration (18 epics, ~0.3 d each) | 6 days rolling |
| **Total** | **~18 days (1 engineer)** |

With 2 engineers split Phase B by category → ~11 days elapsed.
