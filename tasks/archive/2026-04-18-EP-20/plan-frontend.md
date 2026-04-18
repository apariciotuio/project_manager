# EP-20 Frontend Implementation Plan

Blueprint for `develop-frontend`. Each step cites its capability spec and the test boundary. TDD — failing tests first, then implementation.

**Stack**: Next.js 14 App Router · TypeScript strict · Tailwind · `next-themes` · `lucide-react` · `next-intl` · Vitest + RTL · Playwright + `axe-playwright` · `wcag-contrast` (new dev dep).

**Legend**
- `[S:<cap>]` → spec reference (`theme-matrix` for this epic)
- `[T:<kind>]` → `unit` | `integration` | `e2e` | `a11y` | `lint` | `visual`

---

## 0. Pre-flight

- Branch: `feature/EP-20-theme-matrix`
- Feature flag: reuse `DESIGN_SYSTEM_V1` from EP-19 — no new flag
- New dev dep: `wcag-contrast` (for contrast parity test only)
- No backend work, no schema change, no API contract touched

---

## 1. Phase A — Tokens & palette

### 1.1 Matrix palette in `globals.css`  [S:theme-matrix]

1. Append `.matrix { ... }` block to `frontend/app/globals.css` mirroring **every** semantic variable defined in `:root` / `.dark` (see `design.md` Token diff)
2. Append `.matrix body { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace; }`
3. Preserve ordering: `:root` → `.dark` → `.matrix`; comments delimit each block

### 1.2 Token parity test  [T:unit]

1. **RED** — `frontend/__tests__/theme-token-parity.test.ts`. Load `globals.css` via `fs`, extract the three token blocks with a regex, assert `keys(:root) === keys(.dark) === keys(.matrix)`. Fail with a descriptive diff when a key is missing.
2. **GREEN** — parity passes; if not, add missing tokens to `.matrix`

### 1.3 Contrast parity test  [T:unit]

1. **RED** — `frontend/__tests__/theme-contrast.test.ts`. For each theme × each semantic pair `(foreground, background)`:
   - `(--foreground, --background)` → WCAG AA body (≥ 4.5:1)
   - `(--primary-foreground, --primary)` → UI (≥ 3:1)
   - `(--destructive-foreground, --destructive)` → UI
   - `(--muted-foreground, --muted)` → AA body
   - Plus every domain pair (state / severity / tier / level)
2. Use `wcag-contrast`'s `hex` helper; convert HSL → hex in the test helper
3. **GREEN** — tweak Matrix HSL values until every pair passes. Expected weak spots: `--muted-foreground` on `--muted`, `--warning` on Matrix `--background`

### 1.4 Visual smoke

- Boot the dev server, force `<html class="matrix">` via devtools, walk one representative page per area (login, workspace list, item detail, inbox, admin). Legibility + no invisible text + focus rings visible. Human pass, not automated.

---

## 2. Phase B — Trinity helpers

### 2.1 Contract & tests  [T:unit]

`lib/theme/trinity.ts` — pure module, no React.

Public API:

```ts
export type AppTheme = 'light' | 'dark' | 'matrix' | 'system';

export function getPreviousTheme(): AppTheme;
export function setPreviousTheme(theme: AppTheme): void;
export function isRainEnabled(): boolean;
export function setRainEnabled(enabled: boolean): void;
```

**RED** — `lib/theme/trinity.test.ts`:

1. `getPreviousTheme` returns `'system'` when `localStorage` is empty
2. `getPreviousTheme` returns `'system'` when stored value is not in the allowlist (security T1)
3. `getPreviousTheme` returns the stored value when valid (`'dark'`)
4. `setPreviousTheme('light')` writes `trinity:previousTheme = 'light'`
5. `setPreviousTheme` with an invalid value is impossible by type; no runtime check needed
6. `isRainEnabled` defaults to `false` when absent
7. `isRainEnabled` returns `true` only for the exact string `'true'`
8. `setRainEnabled(true)` writes `'true'`; `setRainEnabled(false)` writes `'false'`
9. SSR guard: calling any helper with `typeof window === 'undefined'` returns the safe default and does not throw

### 2.2 Implementation

1. **GREEN** — implement per contract. Storage keys: `trinity:previousTheme`, `trinity:rainEnabled`
2. Allowlist constant: `const THEMES = ['light', 'dark', 'matrix', 'system'] as const`
3. SSR guard via `typeof window !== 'undefined'` wrapper at the top of each accessor

---

## 3. Phase C — ThemeSwitcher

### 3.1 Contract & tests  [T:unit]

Replaces `ThemeToggle`. Segmented control (three buttons) or dropdown — pick **segmented** for desktop, dropdown collapse on ≤ 640 px.

Props: `{ className?: string }`.

**RED** — `components/system/theme-switcher/theme-switcher.test.tsx`:

1. Renders three options labeled `Light`, `Dark`, `System` (via `next-intl`)
2. `aria-pressed` reflects the active option; others are `false`
3. Click on `Light` calls `setTheme('light')`
4. Click on `Dark` calls `setTheme('dark')`
5. Click on `System` calls `setTheme('system')`
6. Hydration safety: first render during SSR shows no active state until `mounted`
7. When current theme is `matrix`, no option shows as active (Matrix is entered via pill only)

### 3.2 Implementation

1. **GREEN** — segmented control using `button` + `aria-pressed`. Icons: `Sun`, `Moon`, `MonitorSmartphone` from `lucide-react`
2. Keyboard: Tab moves between options; Enter/Space activates
3. Focus ring from existing `--ring` token
4. Touch target ≥ 44×44 px on mobile
5. Export from `components/system/theme-switcher/index.ts`

### 3.3 Deprecate `ThemeToggle`

1. Replace `theme-toggle.tsx` body with a re-export: `export { ThemeSwitcher as ThemeToggle } from '@/components/system/theme-switcher';`
2. Add `/** @deprecated use `ThemeSwitcher` */` JSDoc
3. Find all current consumers, swap imports to `ThemeSwitcher` in the same PR:
   ```
   grep -r "ThemeToggle" frontend/app frontend/components
   ```
4. Schedule removal of the re-export one release after merge (tracked in `tasks-frontend.md` §Deferred)

### 3.4 i18n

Add to `frontend/locales/es/theme.json` (tuteo, ES source of truth):

```json
{
  "switcher": {
    "light": "Claro",
    "dark": "Oscuro",
    "system": "Sistema",
    "ariaLabel": "Selector de tema"
  },
  "redPill": {
    "label": "Píldora roja",
    "tooltip": "Entra en Matrix",
    "aria": "Entrar en el tema Matrix"
  },
  "bluePill": {
    "label": "Píldora azul",
    "tooltip": "Salir de Matrix",
    "aria": "Salir del tema Matrix"
  },
  "rain": {
    "toggle": "Lluvia digital",
    "on": "Activar lluvia",
    "off": "Desactivar lluvia"
  },
  "announce": {
    "entered": "Tema Matrix activado",
    "exited": "Saliste del tema Matrix"
  }
}
```

Mirror in `frontend/locales/en/theme.json` with English values.

---

## 4. Phase D — Red pill

### 4.1 Contract & tests  [T:unit]

Props: `{ className?: string }`.

**RED** — `components/system/red-pill/red-pill.test.tsx`:

1. Returns `null` when `useTheme().theme === 'matrix'`
2. Renders an icon-labeled button otherwise
3. Click flow:
   - Calls `trinity.setPreviousTheme(currentTheme)` with the *current* (pre-click) theme
   - Then calls `setTheme('matrix')`
4. `aria-label` from `theme.redPill.aria`
5. Tooltip from `theme.redPill.tooltip`
6. Touch target ≥ 44×44 px (assert via computed style or explicit `min-w/min-h`)
7. SSR/hydration: during the first paint before `mounted`, does not flash the pill (render null)

### 4.2 Implementation  [T:unit + a11y]

1. **GREEN** — `components/system/red-pill/red-pill.tsx`:
   - Icon: `lucide-react` `Pill` with red fill (`fill="currentColor"` + `text-destructive` class — remains a semantic token)
   - Shape: rounded-full, `44×44` px touch area, visually a `32×32` pill inside
   - Tooltip via shadcn `Tooltip` primitive (already installed per EP-19)
   - Live region: after click, announce `t('theme.announce.entered')` via an `aria-live="polite"` span (or push to a global announcer if one exists)
2. `[T:a11y]` — Playwright story with axe; zero violations

---

## 5. Phase E — Blue pill

### 5.1 Contract & tests  [T:unit]

Props: `{ className?: string }`.

**RED** — `components/system/blue-pill/blue-pill.test.tsx`:

1. Returns `null` when `theme !== 'matrix'`
2. Renders otherwise
3. Click flow:
   - Calls `setTheme(trinity.getPreviousTheme())` — allowlist-guarded fallback to `'system'` handled inside trinity
4. `aria-label` from `theme.bluePill.aria`
5. Tooltip from `theme.bluePill.tooltip`
6. Live region announces `t('theme.announce.exited')`

### 5.2 Implementation

1. **GREEN** — mirror of RedPill; icon uses `text-info` (cyan-ish in light/dark, inverted under Matrix — passes contrast via token palette)
2. Export

---

## 6. Phase F — Header wiring

1. Locate the workspace header component (`frontend/app/workspace/**/layout.tsx` or the AppShell from EP-12)
2. Render `<ThemeSwitcher />` and, adjacent, a compact cluster `<RedPill /> <BluePill />` (only one of the two ever renders)
3. Mobile ≤ 640 px: collapse switcher into a dropdown; keep pill cluster visible
4. `[T:e2e]` Playwright — assert all three controls are present on a desktop viewport after login

---

## 7. Phase G — Provider update

1. Edit `frontend/app/providers.tsx`:
   ```tsx
   <ThemeProvider
     attribute="class"
     defaultTheme="system"
     enableSystem
     themes={['light', 'dark', 'matrix']}
     disableTransitionOnChange
   >
   ```
2. Smoke check: no hydration warnings across all 3 themes (manual devtools pass)
3. `[T:integration]` Navigate `/` → set theme to matrix → hard reload → `<html>` has `class="matrix"` on first paint (no FOUC)

---

## 8. Phase H — MatrixRain  [Should — may defer]

### 8.1 Contract & tests  [T:unit]

Renders a fullscreen-background `<canvas>` that animates falling katakana glyphs. Mount-only when all of:
- `theme === 'matrix'`
- `trinity.isRainEnabled() === true`
- `window.matchMedia('(prefers-reduced-motion: reduce)').matches === false`

**RED** — `components/system/matrix-rain/matrix-rain.test.tsx`:

1. Does not render when `theme !== 'matrix'`
2. Does not render when `isRainEnabled() === false`
3. Does not render when `prefers-reduced-motion: reduce`
4. Renders a `<canvas>` when all conditions met
5. On unmount, cancels its `requestAnimationFrame` loop (spy on `cancelAnimationFrame`)
6. Canvas has `aria-hidden="true"`, `pointer-events: none`, `z-index: -1`

### 8.2 Implementation

1. **GREEN** — `matrix-rain.tsx`:
   - Glyph pool: static `const GLYPHS = 'アイウエオ…0123456789'.split('')`
   - Grid: columns = `canvas.width / 16`; each column has a current row
   - rAF loop capped to ~30 fps (`lastFrame + 33 > now` skip)
   - Opacity `0.08 – 0.12` via `ctx.fillStyle = 'rgba(0, 255, 65, 0.1)'`
   - Trail fade: overlay a translucent black rect each frame
   - Handles `resize` via a listener that re-dimensions the canvas
2. Lazy-load via `next/dynamic(() => import('…matrix-rain'), { ssr: false })` — wrapper exports a no-SSR component
3. Rain toggle UI: `components/system/rain-toggle/rain-toggle.tsx` — small switch next to `<BluePill />`, persists via `trinity.setRainEnabled`

### 8.3 Perf gate  [T:lint]

- `size-limit` route budget unchanged — `MatrixRain` adds bundle weight only when dynamically imported

---

## 9. Phase I — E2E & a11y

### 9.1 Theme cycle  [T:e2e]

`frontend/e2e/theme-cycle.spec.ts`:

1. Login → assert `<html>` class and `localStorage.theme`
2. Click `Dark` in switcher → `<html class="dark">`, `localStorage.theme === 'dark'`
3. Click red pill → `<html class="matrix">`, `localStorage['trinity:previousTheme'] === 'dark'`, blue pill visible, red pill gone
4. Click blue pill → `<html class="dark">`, red pill visible
5. Click `Light` → no class on `<html>`, `localStorage.theme === 'light'`
6. Click red pill → Matrix
7. Click `System` → Matrix exits without consulting `trinity:previousTheme`

### 9.2 axe per theme  [T:a11y]

For each theme, visit 3 representative pages (login, workspace items list, item detail), run `injectAxe` + `checkA11y` with `{ includedImpacts: ['serious', 'critical'] }`. Zero violations.

### 9.3 Keyboard walk  [T:e2e]

`Tab` from page top → switcher reachable → pills reachable → all activate via `Enter`. No keyboard trap under Matrix.

### 9.4 Reduced motion  [T:e2e]

Boot Playwright with `reducedMotion: 'reduce'` → enable rain → assert no `<canvas>` element is inserted under Matrix.

---

## 10. Phase J — Cleanup & docs

1. Remove deprecated `ThemeToggle` re-export one release after merge (tracked in `tasks-frontend.md §Deferred`)
2. Append a section to `frontend/docs/ux-principles.md` (create if missing): "Themes & the red-pill metaphor" — document the deliberate flip
3. Storybook: add `matrix` to the theme addon toolbar so each system component renders under all 3 themes (no new story files; existing decorators extend)

---

## File map (new)

```
frontend/
├── app/globals.css                                          (edit — add .matrix block)
├── app/providers.tsx                                        (edit — themes array)
├── lib/theme/
│   ├── trinity.ts                                           (new)
│   └── trinity.test.ts                                      (new)
├── components/system/
│   ├── theme-switcher/
│   │   ├── theme-switcher.tsx                               (new)
│   │   ├── theme-switcher.test.tsx                          (new)
│   │   └── index.ts                                         (new)
│   ├── theme-toggle/theme-toggle.tsx                        (edit — deprecated re-export)
│   ├── red-pill/
│   │   ├── red-pill.tsx                                     (new)
│   │   ├── red-pill.test.tsx                                (new)
│   │   └── index.ts                                         (new)
│   ├── blue-pill/
│   │   ├── blue-pill.tsx                                    (new)
│   │   ├── blue-pill.test.tsx                               (new)
│   │   └── index.ts                                         (new)
│   ├── matrix-rain/                                         (Should)
│   │   ├── matrix-rain.tsx                                  (new)
│   │   ├── matrix-rain.test.tsx                             (new)
│   │   └── index.ts                                         (new)
│   └── rain-toggle/                                         (Should — ships with matrix-rain)
│       ├── rain-toggle.tsx                                  (new)
│       └── index.ts                                         (new)
├── locales/es/theme.json                                    (new)
├── locales/en/theme.json                                    (new)
├── __tests__/
│   ├── theme-token-parity.test.ts                           (new)
│   └── theme-contrast.test.ts                               (new)
└── e2e/theme-cycle.spec.ts                                  (new)
```

## Dependencies / versions

- `wcag-contrast`: `^3.0.0` (dev) — contrast parity test
- No production deps added
- `next-themes`, `lucide-react`, `next-intl` already present

## Done-when

- All Phase A–G + I items green
- Phase H optional for MVP (ships in same PR if time; otherwise follow-up)
- `code-reviewer` agent: no Must Fix
- `review-before-push`: green
- Manual walkthrough under all 3 themes clean
