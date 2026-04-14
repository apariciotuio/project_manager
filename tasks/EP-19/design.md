# EP-19 Technical Design — Design System & Frontend Foundations

> **Decision summary**: adopt shadcn/ui on Radix; copy components into repo. Define semantic tokens in Tailwind + CSS variables. Ship a 25-component domain catalog under `apps/web/src/components/system/`. Inter typography via `next/font`. Custom typed-key i18n (no framework MVP). ES tuteo source of truth with EN stub. ESLint rules enforce tokens, no literal UI strings, and tone. Gate PRs on Lighthouse a11y ≥ 95 and `size-limit`. Storybook 8 as the catalog with a11y add-on. Dark mode MVP. Consumers: every frontend epic (EP-00..EP-18 retrofit, new epics going forward).

---

## 1. Context & Goals

EP-12 already ships layout primitives (`AppShell`, `BottomSheet`, `DataTable`, `EmptyState`, `SkeletonLoader`, `ErrorBoundary`) and API/SSE plumbing. EP-19 layers on top with:

- A **component library choice** (shadcn/ui + Radix)
- **Semantic tokens** and a **typography system**
- **Domain components** shared across every epic (StateBadge, TypeBadge, PlaintextReveal, ConfirmDialog, TagChip, CompletenessBar, CommandPalette, ShortcutCheatSheet, …)
- **Tone + i18n** infrastructure
- **Quality gates** (a11y, performance, tone, lints)

Goal: any frontend engineer starting any epic picks components from a catalog, follows copy guidelines, and focuses on domain logic.

---

## 2. Architecture

```
apps/web/src/
├── app/                          # pages (unchanged)
├── components/
│   ├── layout/                   # EP-12 primitives (kept)
│   ├── ui/                       # shadcn-generated (EP-19 manages install list)
│   └── system/                   # EP-19 domain catalog
│       ├── state-badge/
│       ├── type-badge/
│       ├── level-badge/
│       ├── severity-badge/
│       ├── tier-badge/
│       ├── tag-chip/
│       ├── plaintext-reveal/
│       ├── typed-confirm-dialog/
│       ├── checkbox-confirm-dialog/
│       ├── command-palette/
│       ├── shortcut-cheatsheet/
│       ├── human-error/
│       ├── diff-hunk/
│       ├── completeness-bar/
│       ├── jira-badge/
│       ├── lock-badge/
│       ├── version-chip/
│       ├── rollup-badge/
│       ├── relative-time/
│       ├── copy-button/
│       ├── owner-avatar/
│       ├── user-avatar/
│       └── empty-state-with-cta/
├── hooks/
│   ├── use-auto-clear-plaintext.ts
│   ├── use-copy-to-clipboard.ts
│   ├── use-relative-time.ts
│   ├── use-command-palette.ts
│   ├── use-keyboard-shortcut.ts
│   ├── use-theme.ts
│   └── use-human-error.ts
├── i18n/
│   ├── es/
│   │   ├── common.ts
│   │   ├── errors.ts
│   │   ├── workitem.ts
│   │   ├── review.ts
│   │   ├── hierarchy.ts
│   │   ├── tags.ts
│   │   ├── attachment.ts
│   │   ├── lock.ts
│   │   ├── mcp.ts
│   │   ├── assistant.ts
│   │   └── role.ts
│   ├── en/                       # stub mirror
│   └── index.ts                  # typed `t()` + `I18nProvider`
├── styles/
│   └── globals.css               # CSS variables (light + dark)
├── lib/
│   └── color.ts                  # luminance, contrast helpers
└── stories/                      # Storybook stories
```

CI lint config (new):

```
apps/web/eslint-rules/
├── no-raw-tailwind-color.ts
├── no-raw-text-size.ts
├── no-literal-user-strings.ts
├── tone-jargon.ts
└── tone-jargon.json
```

---

## 3. Key Technical Decisions

### 3.1 shadcn/ui on Radix

Copy-into-repo model. We own the code; no NPM version drift risk. Radix handles accessibility primitives (focus trap, ARIA, keyboard). shadcn gives sensible Tailwind-styled wrappers we can adapt.

Rejected: Material UI, Chakra, Mantine (heavier, more opinionated visually, harder to match the "sin ruido" postura). Custom from scratch (waste of time).

### 3.2 CSS variables + Tailwind `theme.extend`

Variables in `globals.css` for runtime theming (dark mode toggle without rebuild). Tailwind classes map to variable-based colors. Both layers live for the same semantic names, CI enforces parity.

### 3.3 Inter via `next/font/google`

Variable font, tree-shaken. Self-hosted by Next.js. Size-matching fallback prevents CLS.

### 3.4 Custom typed i18n getter

A typed object tree + a thin `t()` function. Pros: zero dependency, full type-checking of keys, small bundle. Cons: no rich ICU plurals — we ship a tiny `icuLite` that handles `plural/one/other` and `select`. When (if) complexity grows, swap in `next-intl` in a single module.

Rejected: `next-intl`, `react-intl` (heavy for our needs); `i18next` (runtime-heavy).

### 3.5 ESLint rules in-repo

`no-raw-tailwind-color`, `no-raw-text-size`, `no-literal-user-strings`, `tone-jargon`. Source lives in `apps/web/eslint-rules/` and is maintained with the codebase. Rules have safelists for valid exceptions (shadcn source, `aria-hidden` presentational strings).

### 3.6 Storybook 8 as the catalog

Every system/domain component has stories with variants + Docs. `@storybook/addon-a11y` runs axe per story. Deployed on PR previews (Vercel preview + Storybook standalone build).

### 3.7 Dark mode MVP

`next-themes` with `system` default. Semantic tokens resolve against `html.dark`. No FOUC via SSR cookie.

### 3.8 Performance budget enforced

`size-limit` config per Next.js route file in `apps/web/size-limit.config.js`. CI fails on breach. Canary Lighthouse posts metrics back to PR as comment.

### 3.9 Migration via `extensions.md`

Each existing epic (EP-00..EP-18) gets a short "EP-19 adoption" patch in `tasks/extensions.md` describing which local components to retire, which semantic tokens to adopt, and which i18n dictionaries to consume. PRs migrate per-epic; no big-bang.

### 3.10 Feature flag `DESIGN_SYSTEM_V1`

Initially opt-in per route. Flipped to required once every existing epic's frontend has migrated. Keeps risk bounded.

---

## 4. Data Model Changes

None — frontend-only.

---

## 5. Security

- `PlaintextReveal` integration test asserts no write to `localStorage`, `sessionStorage`, IndexedDB, cookies, URL, console
- `HumanError` renders text nodes only; no `dangerouslySetInnerHTML`
- Icon library pinned; Renovate bumps
- Theme and i18n values are static build artifacts; no runtime interpolation of user input into CSS or DOM
- Tone linter prevents accidental leakage of technical details to user-facing UI ("token", "API", raw error codes)

---

## 6. Testing Strategy

### Unit
- Each component: happy path + variants + a11y role assertions + prop-type compile check
- `useAutoClearPlaintext`: timing test with fake timers
- `useCopyToClipboard`: clipboard mock + fallback
- `useKeyboardShortcut`: keydown events, form-field suppression

### Integration
- `PlaintextReveal` in a full flow: open → reveal → copy → close → assert purge + no persistence writes
- `CommandPalette`: register shortcuts on one page, unmount, verify cleanup
- `HumanError` with a known and an unknown code

### Visual / a11y
- Storybook with `addon-a11y` runs axe per story (zero `serious+`)
- Lighthouse a11y ≥ 95 on canonical pages (`/`, `/workitems`, `/inbox`, `/admin/mcp-tokens`, `/settings/mcp-tokens`)

### E2E (Playwright)
- Keyboard parity: tab through a page, every interactive is reachable
- `?` opens cheat sheet; `⌘K` opens palette
- Dark-mode toggle: no FOUC, persists across reloads

### Performance
- `size-limit` CI gate per route
- Canary Lighthouse sample on staging

### Lints
- `no-raw-tailwind-color` and friends run in CI; dedicated test fixture with known violations ensures the rules fire

---

## 7. Observability

Minimal — this is UI. Useful signals:
- `unmapped_error_code` event when `HumanError` falls back to generic (indicates missing i18n entry; dev console warn + Sentry if enabled)
- Bundle size posted as GitHub PR comment from `size-limit`
- Lighthouse canary results posted as PR comment

---

## 8. Rollout Plan

1. **Phase A — Foundation (1 week)**: shadcn init, tokens, typography, Inter, dark mode, lint rules, Storybook skeleton
2. **Phase B — Catalog (2 weeks)**: ship all 25 components with stories + tests
3. **Phase C — Migration (rolling)**: one epic per PR, starting with EP-18 (smallest frontend surface), then EP-17, EP-15, EP-16, EP-14, EP-13, EP-11, EP-10, EP-09, EP-08, EP-07, EP-06, EP-04, EP-03, EP-02, EP-01, EP-00
4. **Phase D — Gate flip**: `DESIGN_SYSTEM_V1` becomes the only path; old local components deleted

Rollback: feature flag off; epics continue on their local components while EP-19 fixes forward.

---

## 9. Open Risks

- **Tone linter false positives** — wordlist needs tuning; mitigate with generous safelist and ability to inline-override with `// eslint-disable-line tone-jargon` + review
- **shadcn upstream changes** — since components are copied in, we don't inherit breakage; but syncing bug fixes is manual. Process: quarterly review of shadcn changelog; apply selectively.
- **Migration drag** — existing epics may resist retrofit if they're mid-flight. Solved by feature flag + rolling migration.
- **Design decisions deferred** — brand accent, animations style — are slots in the system; default ships, design fills later.

---

## 10. Dependencies

- EP-12 — layout primitives (already complete; EP-19 extends)
- Nothing else in EP-00..EP-18 is a blocker; EP-19 runs in parallel and retrofits existing plans via `extensions.md`
