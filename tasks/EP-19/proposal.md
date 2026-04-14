# EP-19 — Design System & Frontend Foundations

## Business Need

The platform is used by profiles with very different levels of technical fluency: Product Managers, Tech Leads, Founders, Negocio, QA, Team Leads, Workspace/Project Admins, Superadmins (see functional description §1). A heterogeneous audience needs an interface that **disappears**: quick, obvious, non-intimidating. Nobody should have to "learn the tool" before they can create a work item, resolve a review, or look at a dashboard.

Today the frontend plan in every existing epic (EP-00 through EP-18) makes local decisions about colors, badges, confirmation dialogs, empty states, tone of voice, tag chips, plaintext reveals, command palettes, shortcuts, i18n copy, a11y patterns. Without a shared design system, each epic drifts: different greens for "Ready", different confirmation flows, different terminology (`Draft` vs `Borrador`, `Force Ready` vs `Forzar Ready`), different error message shapes. This hurts usability and compounds maintenance.

EP-12 already ships the **technical chassis** (AppShell, BottomSheet, DataTable, EmptyState, SkeletonLoader, ErrorBoundary, Tailwind mobile-first config, SSE hook). It does **not** own the design language, the component library choice, the semantic color tokens, the tone, or the shared domain components (`StateBadge`, `TypeBadge`, `CompletenessBar`, `PlaintextReveal`, `TagChip`, `ConfirmDialog`, `CommandPalette`). Those are the subject of EP-19.

The aim is that by the time a frontend engineer starts any epic, the "how to paint it" decisions are already made and implemented: pick a component from a catalog, follow the copy guidelines, and focus on the feature's business logic.

## Objectives

- Adopt **shadcn/ui on Radix** as the component library (copy-into-repo model, no vendor lock-in)
- Define and ship **semantic design tokens** in Tailwind (palette, typography, spacing, radii, shadows) — all referenced by semantic name, never raw Tailwind colors
- Ship a **catalog of shared domain components** that every subsequent epic consumes: `<StateBadge>`, `<TypeBadge>`, `<CompletenessBar>`, `<TagChip>`, `<ConfirmDialog>`, `<PlaintextReveal>`, `<CommandPalette>`, `<ShortcutCheatSheet>`, `<JiraBadge>`, `<LockBadge>`, `<RollupBadge>`, `<LevelBadge>`, `<DiffHunk>`
- Define and codify **tone of voice** in Spanish (tuteo, verbos directos, jerga plana) and seed the **i18n base** (ES-ES source of truth + EN mirror stub for future)
- Establish the **accessibility gate**: Lighthouse a11y ≥ 95, axe-core automated, WCAG AA contrast, keyboard parity — blocks merge
- Establish the **performance budget** (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1, per-page bundle ≤ 200 KB gzipped) — monitored in CI
- Publish governance doc `docs/ux-principles.md` as the single source of truth
- Provide a **Storybook** catalog for designers + frontend engineers
- Provide **shared hooks** common to the catalog: `useAutoClearPlaintext`, `useRelativeTime`, `useCopyToClipboard`, `useCommandPalette`, `useKeyboardShortcut`

## Non-Goals

- No business features (all already live in their own epics)
- No backend work (EP-19 is pure frontend + governance)
- No visual brand identity beyond a single accent slot (waiting on design); the system ships with a neutral baseline and a slot for the brand accent that design fills in later
- No component-per-feature library — EP-19 owns **platform-wide** components; feature-specific components stay in their epic (e.g., the Dundun split-view layout stays in EP-03)
- No replacement of EP-12's layout primitives (`AppShell`, `BottomSheet`, `DataTable`, `EmptyState`, `SkeletonLoader`, `ErrorBoundary`, `useSSE`) — EP-19 **consumes and themes** them

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-190 | As a frontend engineer, I install shadcn/ui and register the initial component set from the repo's scripts | Must |
| US-191 | As a frontend engineer, I use semantic color tokens (`bg-primary`, `text-destructive`, `bg-warning`) instead of raw Tailwind classes | Must |
| US-192 | As a frontend engineer, I import `<StateBadge state="ready">` / `<TypeBadge type="story">` and get consistent styling across all epics | Must |
| US-193 | As a frontend engineer, I import `<ConfirmDialog>` for any destructive action and get consistent UX with typed-name and checkbox variants | Must |
| US-194 | As a frontend engineer, I import `<PlaintextReveal>` for any "show once" flow (tokens, credentials) with copy/download/auto-clear | Must |
| US-195 | As a user, pressing `⌘K` / `Ctrl+K` anywhere opens a command palette to search and navigate | Must |
| US-196 | As a user, pressing `?` anywhere opens a shortcut cheat sheet for the current page | Must |
| US-197 | As a user, every screen speaks Spanish with tuteo, direct verbs, no jargon, and humane error messages | Must |
| US-198 | As a user with `prefers-reduced-motion`, animations are disabled; as a user with a screen reader, ARIA is correct; as a user on keyboard, focus is always visible | Must |
| US-199 | As a user on mobile ≤ 375 px, every critical flow (inbox, revisions, confirmations) works with 44×44 px touch targets | Must |
| US-200 | As a designer, I browse the component catalog in Storybook with docs, examples, and a11y notes | Should |
| US-201 | As a maintainer, I run a Chromatic-style visual regression suite in CI to catch accidental style drift | Should |
| US-202 | As a maintainer, I run a bundle-size check per route in CI that fails if the budget is exceeded | Must |

## Acceptance Criteria

### Component library & tokens

- WHEN a frontend engineer runs `pnpm ui:add button` THEN shadcn adds the Radix-backed component into `apps/web/src/components/ui/` and wires the theme tokens
- WHEN any component uses a color THEN it references a semantic token (`bg-primary`, `text-destructive`, `bg-muted`, `text-warning-foreground`, …) — CI fails on raw hex/raw Tailwind-color class in `apps/web/src/`
- WHEN a component needs a state-specific color THEN the mapping is `ready→success`, `in_review→info`, `blocked→warning`, `rejected→destructive`, `draft→muted` — one table, one place
- WHEN `prefers-reduced-motion: reduce` is set THEN all EP-19 animations (toasts, sheets, palette open, skeleton shimmer) are disabled

### Shared domain components

- WHEN `<StateBadge state="ready" />` is rendered THEN it shows text label + semantic color + icon, sized by optional prop (`sm | md | lg`), accessible by screen reader ("Estado: Listo")
- WHEN `<TypeBadge type="story" />` / `milestone` / `epic` / `bug` / `task` / `spike` / `idea` / `change` / `requirement` THEN type-specific icon + label rendered
- WHEN `<CompletenessBar level="low|medium|high|ready" percent={n} />` THEN bar colored by level, percent announced as `aria-valuenow`
- WHEN `<TagChip tag={t} />` THEN chip uses tag.color at 15% bg opacity; text is contrast-computed (white/black from luminance)
- WHEN `<ConfirmDialog mode="typed-name" expected="production" />` THEN submit is disabled until exact match
- WHEN `<PlaintextReveal>` is rendered THEN it enforces: 3 s minimum gate + require reveal/copy/download interaction + 5 min auto-clear + purge on close + no-localStorage/sessionStorage/IndexedDB writes
- WHEN `<CommandPalette>` is open AND user types THEN results combine navigation targets, recent items, and search — selected via keyboard

### Copy & tone

- WHEN any UI string is authored THEN it lives in `apps/web/src/i18n/es/` — no hard-coded strings in JSX for user-visible text
- WHEN an error response matches a known code THEN the UI shows the Spanish humanized message from `i18n/es/errors.ts`; unknown codes map to `genericError`
- AND the tone linter (custom lint rule) rejects English UI strings, formal "usted", and jargon from a configured wordlist ("submit", "Ready", "Draft" in user-visible strings)

### Accessibility gate

- AND every Playwright E2E test runs axe-core; any violation of severity ≥ `serious` fails the build
- AND Lighthouse a11y score ≥ 95 is a required check on every PR touching `apps/web/`
- AND focus styles (`ring-2 ring-ring ring-offset-2`) are present on every interactive component in the catalog
- AND keyboard coverage: every action reachable via keyboard with a documented shortcut or standard Tab sequence

### Performance budget

- AND CI runs `size-limit` per Next.js route; any route over 200 KB gzipped fails
- AND LCP, INP, CLS are sampled on a canary deployment; regressions over threshold post a PR comment

### Storybook

- AND every component in the catalog has a Storybook story with variants, controls, and docs
- AND Storybook is deployed on PR previews

### Governance

- AND `docs/ux-principles.md` is the authoritative doc; PR template requires a link when introducing new UI
- AND new shared components can only be added under `apps/web/src/components/ui/` (shadcn) or `apps/web/src/components/system/` (domain); anything else is feature-scoped

## Technical Notes

### Component library

- **shadcn/ui** on Radix — copy-into-repo (`pnpm dlx shadcn@latest add <component>`), zero lock-in
- Initial install: `button`, `dialog`, `alert-dialog`, `dropdown-menu`, `input`, `label`, `select`, `textarea`, `toast`, `table`, `badge`, `tabs`, `sheet`, `tooltip`, `separator`, `skeleton`, `card`, `command`, `popover`, `scroll-area`, `avatar`, `checkbox`, `radio-group`, `switch`, `progress`, `combobox`

### Design tokens

- Implemented in `apps/web/src/styles/globals.css` as CSS variables + Tailwind `theme.extend`
- Semantic tokens: `--background`, `--foreground`, `--card`, `--primary`, `--primary-foreground`, `--secondary`, `--destructive`, `--destructive-foreground`, `--success`, `--warning`, `--info`, `--muted`, `--muted-foreground`, `--accent`, `--ring`, `--border`
- Domain tokens: `--state-draft`, `--state-in-review`, `--state-ready`, `--state-blocked`, `--state-archived`, `--state-exported`; `--severity-blocking`, `--severity-warning`, `--severity-info`; `--tier-1`, `--tier-2`, `--tier-3`, `--tier-4`
- Typography tokens: sizes, weights, line-heights per semantic role (display, h1, h2, body, caption, code)
- Light + dark palettes; system-preference follows `html.dark` class via `next-themes`

### Typography

- **Inter** (variable font) via `next/font/google`
- Size/weight scale defined as Tailwind semantic classes (`text-display`, `text-h1`, `text-body`, `text-caption`, `text-code`)
- Never use raw `text-3xl`/`font-bold` in feature code — CI lint rule enforces

### Shared components — catalog

Located under `apps/web/src/components/system/`:

`StateBadge`, `TypeBadge`, `CompletenessBar`, `LevelBadge` (low/medium/high/ready), `TagChip`, `TagChipList`, `JiraBadge`, `LockBadge`, `RollupBadge`, `SeverityBadge` (blocking/warning/info), `TierBadge` (inbox 1..4), `DiffHunk` (added/removed/context), `VersionChip`, `OwnerAvatar`, `UserAvatar`, `TypedConfirmDialog`, `CheckboxConfirmDialog`, `PlaintextReveal`, `CommandPalette`, `ShortcutCheatSheet`, `RelativeTime`, `CopyButton`, `EmptyStateWithCTA` (thin wrapper over EP-12's `EmptyState` with canonical CTA placement), `HumanError` (maps error code → localized message).

### Shared hooks

`useAutoClearPlaintext(ms)`, `useRelativeTime(iso)`, `useCopyToClipboard()`, `useCommandPalette()`, `useKeyboardShortcut(combo, handler)`, `useTheme()`, `useLocale()`, `useHumanError(code)`.

### i18n

- Format: typed ES dictionary under `apps/web/src/i18n/es/*.ts` grouped by domain (`common`, `errors`, `auth`, `workitem`, `review`, `hierarchy`, `tags`, `attachments`, `lock`, `mcp`, …)
- Runtime: simple typed getter `t("workitem.state.ready")`; no framework bloat (no next-intl for MVP, escape hatch if plural-heavy)
- Lint: custom ESLint rule `no-literal-user-strings` forbids literal strings in JSX children and common prop positions (`label`, `placeholder`, `aria-label`, `title`)
- Tone-linter: ESLint rule with a jargon wordlist

### Tooling

- **Storybook 8** with `@storybook/addon-a11y`, `@storybook/addon-docs`, Chromatic (optional)
- **size-limit** for bundle budgets
- **axe-playwright** in E2E
- **next-themes** for dark mode
- **@dnd-kit** only if EP-19 has DnD components to share; else it lives in its feature epic
- **lucide-react** as the icon set (consistent, tree-shakable)

### Migration of existing epics

EP-00 through EP-18 `tasks-frontend.md` files are updated via `extensions.md` to:
- Add a "Follows EP-19" preamble
- Replace locally-invented components with EP-19 catalog entries (`StateChip` → `StateBadge`, local `PlaintextReveal` → EP-19's, local confirmation dialog → `TypedConfirmDialog`)
- Point color decisions to semantic tokens instead of raw Tailwind colors
- Reference EP-19's i18n dictionary for shared terms

### Feature flag

`DESIGN_SYSTEM_V1` — opt-in initially per route; flipped to required once all existing epics' frontend work has been migrated.

## Dependencies

- **EP-12** — layout primitives. EP-19 builds on top, does not replace.
- **EP-10** — admin surface (theme preference could live here; not MVP)
- All other frontend epics **depend on EP-19** going forward.

## Complexity Assessment

**Medium**. No novel technology, no complex distributed problem. Real work is:
- Breadth (~25 shared components, i18n structure, tokens, lints, CI gates)
- Careful tone/terminology work (not trivial at product level)
- Retrofitting existing epic plans (minor edits, broad reach)
- Storybook authoring discipline

## Risks

| Risk | Mitigation |
|---|---|
| Bikeshedding on palette and tone delays delivery | Ship with a defensible default (neutral zinc + named state colors + ES tuteo); design review happens **after** the system exists |
| Over-abstraction (building components nobody uses) | Only ship components that at least 2 existing epics in EP-00..EP-18 need; defer the rest |
| Breaking changes cascade to all epics | Semver the component API; deprecation window ≥ 30 days; Storybook docs carry migration notes |
| A11y gate blocks too many PRs | Start with axe rules at "serious+" only; escalate gradually |
| i18n mass migration is tedious | Provide a codemod for the simplest cases; accept hand-work for the rest |
| Lock-in via shadcn folder bloat | shadcn components live in-repo; we OWN them; no risk of upstream breakage |

## Open Questions

1. **Brand accent color** — who owns? **Recommend**: slot in the system, design fills in later; ship neutral until then
2. **Dark mode** — MVP or defer? **Recommend**: MVP; costs are small if baked into tokens from day one
3. **next-intl vs custom** — MVP or defer? **Recommend**: custom typed getter MVP; switch if pluralization becomes painful
4. **Visual regression (Chromatic)** — MVP or defer? **Recommend**: defer; land Storybook first, Chromatic next phase
5. **Icon library** — lucide vs phosphor? **Recommend**: lucide; shadcn already wires it
6. **Spanish/English source** — ES source, EN mirror stub, or EN source with ES translation? **Recommend**: ES source of truth, EN stub; platform's primary audience is ES-speaking

## Out of Scope

- Feature-specific components (they live in their feature epic)
- Branding (logo, marketing pages)
- Public documentation site (use Storybook for internal)
- Plugin system for third-party UI extensions
