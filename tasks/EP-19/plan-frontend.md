# EP-19 Frontend Implementation Plan

Blueprint for `develop-frontend`. Each step cites its capability spec and the test boundary. TDD where the unit has logic; Storybook-first for pure presentational components.

**Stack**: Next.js 14 App Router · TypeScript strict · Tailwind · shadcn/ui on Radix · `next-themes` · `lucide-react` · Storybook 8 · `size-limit` · Playwright + `axe-playwright` · ESLint with custom rules.

**Legend**
- `[S:<cap>]` → spec reference
- `[T:<kind>]` → unit | integration | e2e | a11y | lint | visual

---

## 0. Pre-flight

- Branch: `feature/EP-19-design-system`
- CI: add `ui:lint` job (new ESLint rules), `ui:size` (size-limit), `ui:a11y` (axe on Storybook), `ui:storybook` (build Storybook)
- Feature flag: `DESIGN_SYSTEM_V1` default off; switches routes to the new catalog when true

---

## 1. Phase A — Foundation

### 1.1 Tokens & theming  [S:tokens-and-theming]

1. Define semantic token names (see `design.md` §3.2). Write the contract first — `apps/web/src/styles/tokens.ts` exporting a typed map of token keys.
2. Implement in `globals.css` using CSS variables. Write parity test `[T:unit]` asserting every key in `tokens.ts` has both `:root` and `.dark` values.
3. Update `tailwind.config.ts` — `theme.extend.colors = semanticColors`, `theme.extend.fontSize = semanticSizes`.
4. Add `html.dark` class via `next-themes` in `app/layout.tsx`; SSR cookie.
5. Lint rule `no-raw-tailwind-color`:
   - `[T:lint]` fixture file with `bg-blue-500` fails
   - `[T:lint]` shadcn-sourced file passes (safelist: `src/components/ui/**`)
6. Lint rule `no-raw-text-size`:
   - `[T:lint]` fixture with `text-3xl` fails
   - Passes with `text-h1`

### 1.2 Typography

1. `app/layout.tsx`: `const inter = Inter({ subsets: ['latin', 'latin-ext'], variable: '--font-inter', display: 'swap' })`
2. Tailwind: `fontFamily.sans = ['var(--font-inter)', ...fallbacks]`; fallback size-matched to prevent CLS (use `next/font` built-in)
3. Semantic sizes as Tailwind classes — `text-display`, `text-h1`, `text-h2`, `text-body` (default), `text-caption`, `text-code`
4. Storybook story `Typography/Scale` — renders all semantic sizes in light + dark

### 1.3 Icon library

1. Install `lucide-react`; pin version
2. Lint rule disallows `react-icons`, `@heroicons/*`, `phosphor-react`

### 1.4 shadcn initial install

1. `pnpm dlx shadcn@latest init` — prompts, commit `components.json`
2. `pnpm dlx shadcn@latest add button dialog alert-dialog dropdown-menu input label select textarea toast table badge tabs sheet tooltip separator skeleton card command popover scroll-area avatar checkbox radio-group switch progress combobox`
3. `[T:lint]` CI asserts every file under `components/ui/` references only semantic tokens (regex check)

### 1.5 i18n base  [S:copy-tone-i18n]

1. Define dictionary schema — typed tree under `apps/web/src/i18n/es/*.ts`
2. Implement `t()` with `keyof`-typed argument (compile-time key checking)
3. Implement `icuLite` for `plural` and `select`
4. `[T:unit]` key miss compile-rejected (type-level test with `@ts-expect-error`)
5. `[T:unit]` plural resolution: 0, 1, many
6. `I18nProvider` wrapping app; SSR-safe
7. Seed ES dictionaries per design §2 listing
8. Stub EN mirror (same keys, English values)
9. Lint rule `no-literal-user-strings`:
   - `[T:lint]` `<button>Save</button>` fails
   - `[T:lint]` `<span aria-hidden>—</span>` passes
   - `[T:lint]` `<button>{t('common.save')}</button>` passes
10. Lint rule `tone-jargon`:
    - Wordlist in `tone-jargon.json`
    - `[T:lint]` dictionary entry "Are you sure?" fails
    - `[T:lint]` "¿Quieres continuar?" passes

### 1.6 Storybook

1. `pnpm dlx storybook@latest init`
2. Configure `@storybook/addon-a11y`, `@storybook/addon-docs`, `@storybook/addon-interactions`
3. Global decorators: `I18nProvider`, `ThemeProvider`, `next-themes` toggle in toolbar
4. PR preview deploy via `chromatic` or Vercel (decide based on repo convention)

---

## 2. Phase B — Shared Catalog

For each component the recipe is identical. I document the recipe once and list per-component particulars.

### 2.1 Recipe (repeat for every component)

1. **[T:unit]** Author tests for contract — variant prop types, renders expected markup, a11y role
2. **[T:a11y]** axe assertions in the story; zero `serious+` violations
3. Author component under `components/system/<component-name>/index.tsx`, using shadcn primitives from `components/ui/*`
4. **Storybook story** under `components/system/<component-name>/<name>.stories.tsx`:
   - Variants (every state/size)
   - Interactive controls
   - Dark-mode variant (via theme toggle)
   - A11y notes in Docs tab
5. Export from `components/system/index.ts`
6. `[T:unit]` run; `[T:a11y]` run; Storybook build passes

### 2.2 Particulars per component

#### StateBadge  [S:shared-components#StateBadge]

Props: `{ state: 'draft'|'in_review'|'ready'|'blocked'|'archived'|'exported'; size?: 'sm'|'md'|'lg'; withIcon?: boolean }`. Label via `t(\`workitem.state.\${state}\`)`. Color via `bg-state-\${state}`. `sr-only` span with `Estado: <label>`.

#### TypeBadge

Props: `{ type: WorkItemType; size?; withIcon?: boolean }`. Icon map in `components/system/type-badge/icons.ts`. Label via `t('workitem.type.<type>')`.

#### LevelBadge, SeverityBadge, TierBadge, JiraBadge, LockBadge, VersionChip, RollupBadge

Same pattern, domain-specific tokens and icons.

#### TagChip

Props: `{ tag: Tag; removable?: boolean; onRemove?: () => void }`. Color computation: `colorToBg15(tag.color)` + `contrastText(tag.color)` — implement in `lib/color.ts`. Cache per color via `Map`.

#### CompletenessBar

Props: `{ level: 'low'|'medium'|'high'|'ready'; percent: number; label?: string }`. `role="progressbar"`, `aria-valuenow`, `aria-valuemin=0`, `aria-valuemax=100`.

#### TypedConfirmDialog

Composition over `<AlertDialog>` from shadcn. Props: `{ open, onOpenChange, title, description, expected, confirmLabel, onConfirm, destructive? }`. Submit disabled until `value === expected`; destructive tone applies `bg-destructive`.

**[T:integration]** open → type wrong → submit disabled → type right → submit enabled → click → `onConfirm` called.

#### CheckboxConfirmDialog

Same pattern but gated by a checkbox instead of typed name. `label` prop defaults to `t('common.confirm.understandIrreversible')`.

#### PlaintextReveal  [S:shared-components#PlaintextReveal]

Props:
```ts
{
  value: string,
  open: boolean,
  onClose: () => void,
  title?: string,
  body?: string,
  copyLabel?: string,
  copiedLabel?: string,
  downloadFilename?: string,
  minInteractionGate?: boolean,   // default true
  autoClearMs?: number,           // default 5 * 60 * 1000
  gateSeconds?: number,           // default 3
}
```

Internal state: `revealed`, `copied`, `downloaded`, `gateElapsed`, `cleared`. Close button disabled until `(revealed || copied || downloaded) && gateElapsed`.

On `open` true → start gate timer (`gateSeconds`) and auto-clear timer (`autoClearMs`). On `open` false → clear both timers, purge `value` from internal state.

**[T:integration]** mandatory:
- close button disabled for 3 s on open
- close button remains disabled until interaction
- copy writes to clipboard (mock) + swaps label to `copiedLabel` for 2 s
- download creates a `Blob` with `value` + anchor click (JSDOM mock); no network
- autoClear after `autoClearMs` wipes DOM and state
- **no-persistence test**: spy on `localStorage.setItem`, `sessionStorage.setItem`, `document.cookie` setter, `indexedDB.open` — **zero calls** during the entire flow
- close emits `onClose` with value already purged; re-opening requires a fresh `value` prop

**[T:a11y]** focus trap works; Escape closes only when allowed; `aria-label` on reveal toggle.

#### CopyButton

Props: `{ value, label?, copiedLabel?, onCopied? }`. Uses `useCopyToClipboard`. Confirmation flashes for 2 s.

#### CommandPalette  [S:shared-components#CommandPalette]

Built over shadcn's `<Command>`. Global keyboard listener for `⌘K`/`Ctrl+K`. Registry populated via `useCommandPaletteRegistry(commands)` — each page registers its commands on mount, unregisters on unmount. Categories: Navegación / Recientes / Búsqueda. Search results via debounced fetch hook `useGlobalSearch(q)` (implemented later in EP-13; stub for now).

**[T:integration]** open via shortcut, type, select, close; registry lifecycle across mount/unmount.

#### ShortcutCheatSheet

Global keyboard listener for `?` (suppressed when focus inside form fields). Reads from the same registry as `useKeyboardShortcut`. Grouped by section. Close on Escape.

#### HumanError

Props: `{ code: string; correlationId?: string }`. Resolves `t(\`errors.\${code}\`)`, fallback `t('errors.generic')`. Disclosure (`<Collapsible>`) shows technical details (code + correlation id).

#### DiffHunk

Presentational. Props: `{ kind: 'added'|'removed'|'context'; text: string }`.

#### RelativeTime

Props: `{ iso: string; refreshMs?: number }`. Wraps `<time datetime>`; re-renders on interval (respects `prefers-reduced-motion`). Uses `Intl.RelativeTimeFormat('es')`.

#### EmptyStateWithCTA

Wraps EP-12's `<EmptyState>`. Enforces canonical CTA placement (primary action in the bottom-right). Props: `{ title, description?, illustration?, primaryAction?: { label, onClick }, secondaryAction? }`.

#### OwnerAvatar / UserAvatar

Built over shadcn's `<Avatar>`. Props: `{ user: { id, display_name, avatar_url? } }`. Falls back to initials if no `avatar_url`.

### 2.3 Shared hooks

- `useAutoClearPlaintext(ms)` — uses refs + fake-timer tests
- `useCopyToClipboard()` — returns `{ copy, copied }`; handles unsecure-context fallback with `document.execCommand('copy')` textarea trick; logs warning if neither works
- `useRelativeTime(iso, refreshMs?)` — `useSyncExternalStore` against 1-Hz ticker
- `useCommandPalette()` — open/close state, registry
- `useKeyboardShortcut(combo, handler, options?)` — parses `Mod+K`, `Shift+G`; skips when focus in `INPUT | TEXTAREA | SELECT | contentEditable`
- `useHumanError(code)` — resolves + reports unmapped
- `useTheme()` — wraps next-themes

---

## 3. Phase C — Migration

Executed in rolling PRs, one epic per PR. Each retrofit:

1. Replace locally-defined components with catalog imports
2. Replace string literals with i18n keys (add new entries to the appropriate dictionary if missing)
3. Replace raw-color classes with semantic tokens
4. Delete local component + its tests; reference EP-19 Storybook in epic docs
5. Ensure the page still passes a11y + size-limit + tone lints
6. Mark the retrofit checkbox in `tasks/EP-19/tasks-frontend.md#Phase-C`

Order from smallest to largest frontend surface (see `tasks-frontend.md` §Phase C).

---

## 4. Quality gates

Runs on every PR touching `apps/web/`:

- `ui:lint` — ESLint with custom rules (`no-raw-tailwind-color`, `no-raw-text-size`, `no-literal-user-strings`, `tone-jargon`)
- `ui:a11y` — axe on Storybook stories (zero `serious+`)
- `ui:size` — `size-limit` per route (200 KB gzipped)
- `ui:storybook` — Storybook builds and deploys preview
- Playwright a11y suite runs axe-playwright on E2E scenarios (zero `serious+`)
- Lighthouse canary on 5 pages (`/`, `/workitems`, `/inbox`, `/admin/mcp-tokens`, `/settings/mcp-tokens`); a11y ≥ 95

---

## 5. File structure (target)

```
apps/web/
├── .storybook/
│   ├── main.ts
│   ├── preview.tsx           # global decorators (I18nProvider, ThemeProvider)
│   └── manager.ts
├── eslint-rules/
│   ├── no-raw-tailwind-color.ts
│   ├── no-raw-text-size.ts
│   ├── no-literal-user-strings.ts
│   ├── tone-jargon.ts
│   └── tone-jargon.json
├── size-limit.config.js
├── components.json              # shadcn config
├── src/
│   ├── app/layout.tsx           # Inter + I18nProvider + ThemeProvider
│   ├── components/
│   │   ├── layout/              # EP-12 (existing)
│   │   ├── ui/                  # shadcn (Phase A.2)
│   │   └── system/              # EP-19 domain catalog (Phase B)
│   ├── hooks/                   # Phase B.3
│   ├── i18n/
│   │   ├── es/*.ts
│   │   ├── en/*.ts
│   │   └── index.ts
│   ├── lib/
│   │   └── color.ts
│   └── styles/
│       ├── globals.css
│       └── tokens.ts
└── stories/                     # one story file per system component
```

---

## 6. Effort estimate

| Phase | Work | Est. |
|---|---|---|
| A.1 Tokens | 1 d |
| A.2 Typography + icons | 0.5 d |
| A.3 shadcn install | 0.5 d |
| A.4 Lint rules | 1 d |
| A.5 i18n base + seed | 1 d |
| A.6 Storybook scaffolding | 0.5 d |
| B Catalog (25 components + hooks) | 8 d |
| C Migration (18 epics) | 6 d rolling |
| **Total** | | **~18 d (1 eng)** / ~11 d with 2 engs |

---

## 7. Open items

1. Chromatic visual regression — PoC during Phase B, decide GA post-catalog
2. Brand accent color decision — design side, slotted in tokens
3. Global navigation rename after i18n lands — schedule a UX copy review session mid-Phase B
