# EP-20 — Design

## Scope

Frontend-only. Three themes (`light`, `dark`, `matrix`) + `system` auto-resolve. Red pill / blue pill affordances. localStorage persistence. No backend, no schema, no API.

## Decisions

### D1 — Theme count & registration

**Decision**: Register three themes in `next-themes` (`light`, `dark`, `matrix`) with `enableSystem` preserved for light/dark auto-resolve.

**Alternatives considered**:
- **(a)** Keep 2 themes, make Matrix a CSS class stacked on top of `.dark` via a side-channel toggle. Rejected — bifurcates the theme model and would confuse hydration.
- **(b)** Ship Matrix as a separate `ThemeProvider` wrapper. Rejected — double provider, double storage, no gain.
- **(c)** (chosen) Single `next-themes` provider with three themes. Cleanest, matches the library's intended use.

**Why**: One source of truth, `next-themes` handles class application + hydration + storage. Extending from 2 to 3 is trivial.

### D2 — Red pill placement

**Decision**: Place `RedPill` (and its Matrix-mode sibling `BluePill`) in the **header toolbar, immediately next to the `ThemeSwitcher`**.

**Alternatives**:
- **(a)** Fixed floating button (bottom-right). Rejected — clutters every page, collides with BottomSheet on mobile
- **(b)** Hidden behind Konami code. Rejected — user asked for "un botón", and hidden easter eggs fail discoverability
- **(c)** (chosen) Header toolbar, adjacent to `ThemeSwitcher`. Discoverable, one spot, no collision

### D3 — Digital rain default

**Decision**: Ship digital rain **off by default**, opt-in via a small toggle visible only in Matrix mode. Unconditionally disabled for `prefers-reduced-motion`.

**Why**: Rain is cosmetic and can hurt low-end hardware. The Matrix palette itself delivers 90% of the visual punch. Opt-in is the safe default.

### D4 — Trinity naming convention

**Decision**: Name the helper module `lib/theme/trinity.ts`. It is **not** coupled to the future Trinity endpoint; it is a thematic reference. Storage keys use the `trinity:` prefix (`trinity:previousTheme`, `trinity:rainEnabled`) to reserve the namespace without committing to any remote protocol.

**Why**: Keeps the nod to the future endpoint visible in the code without creating coupling. When the real Trinity integration lands, it gets its own epic and its own module (likely under `lib/integrations/trinity/`).

### D5 — Deprecation of `ThemeToggle`

**Decision**: Introduce `ThemeSwitcher` as the replacement. Keep `ThemeToggle` as a deprecated re-export for **one release**, then remove.

**Why**: `ThemeToggle` is a binary light↔dark toggle that ignores `system` and cannot express a third theme. Forcing a rename now avoids two UIs drifting. One-release grace window is enough — the component has a small blast radius (consumed in header only).

### D6 — Token parity enforcement

**Decision**: Add a CI test (`theme-token-parity.test.ts`) that parses `globals.css` and asserts every CSS variable defined in `:root` also exists in `.dark` **and** `.matrix`. Fails the build on missing tokens.

**Why**: The existing project already enforces light/dark parity informally. With three themes, silent drift is inevitable unless mechanized. Cheap test, high signal.

### D7 — Contrast verification

**Decision**: Add a `theme-contrast.test.ts` suite that, for each theme, asserts every foreground/background semantic pair meets WCAG AA (4.5:1 for body, 3:1 for large text and UI components). Runs in Vitest (headless — read tokens from CSS + compute with a standard WCAG library like `wcag-contrast`).

**Why**: Matrix's phosphor green on near-black *passes* AAA for body — but `--warning` (amber) on the Matrix background or `--muted-foreground` on surfaces could regress. Mechanizing prevents rot.

### D8 — SSR & hydration

**Decision**: Keep the existing `suppressHydrationWarning` on `<html>` + `disableTransitionOnChange` on `ThemeProvider`. Nothing new. Matrix rides the same hydration path as `dark`.

## Component architecture

```
components/system/
├── theme-switcher/
│   ├── theme-switcher.tsx      (segmented: light | dark | system)
│   ├── theme-switcher.test.tsx
│   └── index.ts
├── red-pill/
│   ├── red-pill.tsx            (button, visible when theme !== 'matrix')
│   ├── red-pill.test.tsx
│   └── index.ts
├── blue-pill/
│   ├── blue-pill.tsx           (button, visible when theme === 'matrix')
│   ├── blue-pill.test.tsx
│   └── index.ts
├── matrix-rain/                (Should, not Must)
│   ├── matrix-rain.tsx         (canvas background)
│   ├── matrix-rain.test.tsx
│   └── index.ts
└── theme-toggle/               (DEPRECATED: re-export of ThemeSwitcher for one release)

lib/theme/
├── trinity.ts                  (enterMatrix, exitMatrix, getPreviousTheme, setPreviousTheme)
└── trinity.test.ts
```

## Token diff (summary)

Add block in `app/globals.css` after the `.dark` block:

```css
.matrix {
  /* Base */
  --background: 120 20% 4%;         /* near-black with green tint */
  --foreground: 135 100% 50%;       /* phosphor green #00FF41 */

  /* Card / Popover */
  --card: 120 20% 6%;
  --card-foreground: 135 100% 50%;
  --popover: 120 20% 6%;
  --popover-foreground: 135 100% 50%;

  /* Primary */
  --primary: 135 100% 50%;
  --primary-foreground: 120 20% 4%;

  /* Secondary / Muted / Accent */
  --secondary: 135 30% 12%;
  --secondary-foreground: 135 100% 50%;
  --muted: 135 30% 10%;
  --muted-foreground: 135 60% 60%;
  --accent: 135 30% 14%;
  --accent-foreground: 135 100% 50%;

  /* Destructive / Success / Warning / Info */
  --destructive: 0 100% 55%;
  --destructive-foreground: 0 0% 100%;
  --success: 135 100% 50%;
  --success-foreground: 120 20% 4%;
  --warning: 45 100% 55%;
  --warning-foreground: 120 20% 4%;
  --info: 180 100% 50%;
  --info-foreground: 120 20% 4%;

  /* Border / Input / Ring */
  --border: 135 60% 20%;
  --input: 135 60% 20%;
  --ring: 135 100% 50%;

  /* Domain tokens — state / severity / tier / level */
  /* ...mirror of :root/.dark with phosphor-adjusted values... */
}

.matrix body {
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

Complete list of domain tokens (state/severity/tier/level) follows the same pattern — enforced by `theme-token-parity.test.ts`.

## Trinity helpers (API sketch)

```ts
// lib/theme/trinity.ts
import type { Theme } from 'next-themes';

const PREVIOUS_KEY = 'trinity:previousTheme';
const RAIN_KEY = 'trinity:rainEnabled';

export function getPreviousTheme(): Theme {
  return (localStorage.getItem(PREVIOUS_KEY) as Theme) ?? 'system';
}

export function setPreviousTheme(theme: Theme): void {
  localStorage.setItem(PREVIOUS_KEY, theme);
}

export function isRainEnabled(): boolean {
  return localStorage.getItem(RAIN_KEY) === 'true';
}

export function setRainEnabled(enabled: boolean): void {
  localStorage.setItem(RAIN_KEY, String(enabled));
}
```

Consumed by `RedPill` / `BluePill` / `MatrixRain`. Pure; no React dependencies so unit-testable without a DOM.

## Flow diagrams

### Enter Matrix

```
User clicks RedPill
  → trinity.setPreviousTheme(currentTheme)
  → setTheme('matrix')
  → html.class = 'matrix'
  → RedPill unmounts, BluePill mounts
  → (if rainEnabled && !reducedMotion) MatrixRain mounts
```

### Exit Matrix

```
User clicks BluePill
  → const prev = trinity.getPreviousTheme()
  → setTheme(prev ?? 'system')
  → html.class = prev-resolved
  → BluePill unmounts, RedPill mounts
  → MatrixRain (if mounted) unmounts
```

### First-load

```
No stored theme        → prefers-color-scheme → light | dark
Stored theme = 'light' → html has no class
Stored theme = 'dark'  → html.dark
Stored theme = 'matrix' → html.matrix  (RedPill hidden, BluePill shown)
```

## Testing strategy

| Layer | What | Tool |
|---|---|---|
| Unit | `trinity.ts` helpers | Vitest (mock localStorage) |
| Unit | `ThemeSwitcher` renders segmented + calls `setTheme` | Vitest + RTL |
| Unit | `RedPill` visible when theme != matrix; calls `enterMatrix` | Vitest + RTL |
| Unit | `BluePill` visible when theme == matrix; calls `exitMatrix` | Vitest + RTL |
| Unit | Token parity — `:root` ⊇ `.dark` ⊇ `.matrix` | Vitest (parse CSS) |
| Unit | Contrast AA across all 3 themes | Vitest + `wcag-contrast` |
| Integration | Persist across route changes | Playwright |
| E2E | Full cycle: light → dark → matrix → blue pill → dark; verify html class + localStorage | Playwright |
| E2E a11y | axe-core per theme | Playwright + `axe-playwright` |

## What we are *not* building

- Theme sync to backend (out of scope; localStorage only)
- Theme-per-workspace overrides
- Custom palette editor
- Trinity endpoint wiring (separate future epic)
- Any new shared component beyond the four listed
- Reworking existing components — they inherit Matrix via tokens

## Security approach

Theme state is non-privileged UI. No PII, no tokens, no server calls. Three concrete controls apply:

1. **Allowlist on read** — `trinity.getPreviousTheme()` returns `'light' | 'dark' | 'matrix' | 'system'` only; any foreign value from `localStorage` is coerced to `'system'`. Prevents class-name injection via a poisoned store
2. **Compile-time `setTheme` call sites** — only the four theme components call `setTheme(...)` and always with a string literal. A follow-up ESLint rule can enforce this
3. **Static rain glyph pool** — the `MatrixRain` canvas iterates a hard-coded katakana/digit array. Zero interpolation from user input, URL params, or storage. No path for a canvas-based injection

Full threat model and mitigations live in `specs/theme-matrix/spec.md §Security considerations`.

## Rollout

1. Ship behind the `DESIGN_SYSTEM_V1` flag already present from EP-19 — same flag, same lifecycle
2. Dogfood internally for 1 week
3. Remove deprecated `ThemeToggle` re-export one release after merge

## Tradeoffs accepted

- Three-theme palette means ~1 KB extra CSS shipped to every user, whether they use Matrix or not. Acceptable — the alternative (code-split per theme) is over-engineering for a cosmetic variant.
- Digital rain as `<canvas>` adds one layer to the DOM when active. Mitigated by `z-index: -1`, `pointer-events: none`, 30 fps cap, and unmount-on-exit.
- The red-pill / blue-pill metaphor is cinematically reversed (red = exit the Matrix in the film). We flip it on purpose for the UX mental model ("red = dive in"). Documented in tooltip copy.
