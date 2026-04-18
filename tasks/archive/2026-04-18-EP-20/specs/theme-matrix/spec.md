# Spec — theme-matrix

## Capability

Add a third theme (`matrix`) to the platform, expose a red-pill / blue-pill toggle, and replace the binary `ThemeToggle` with a three-way `ThemeSwitcher` (`Light` / `Dark` / `System`).

## Scenarios

### S1 — Default theme resolution on first load

**WHEN** a user visits the app for the first time AND no theme is stored in `localStorage`
**AND** the OS reports `prefers-color-scheme: dark`
**THEN** `<html>` has the `class="dark"` attribute
**AND** Matrix mode is NOT auto-applied
**AND** the red pill button is visible in the header toolbar

### S2 — User selects Dark from the switcher

**WHEN** the user clicks `Dark` in the `ThemeSwitcher`
**THEN** `<html>` gets `class="dark"`
**AND** `localStorage.theme === 'dark'`
**AND** the switcher reflects `Dark` as selected (`aria-pressed="true"` on the Dark option)

### S3 — User enters Matrix via the red pill

**WHEN** the current theme is `dark`
**AND** the user clicks the red pill
**THEN** `localStorage['trinity:previousTheme'] === 'dark'`
**AND** `<html>` gets `class="matrix"`
**AND** the red pill is hidden
**AND** the blue pill is rendered in its place
**AND** the body font family switches to monospace
**AND** all semantic tokens resolve to the Matrix palette

### S4 — User exits Matrix via the blue pill

**WHEN** the current theme is `matrix`
**AND** `localStorage['trinity:previousTheme'] === 'dark'`
**AND** the user clicks the blue pill
**THEN** `<html>` gets `class="dark"`
**AND** the blue pill is hidden
**AND** the red pill is rendered
**AND** body font returns to the default sans stack

### S5 — User exits Matrix via the theme switcher (alternative path)

**WHEN** the current theme is `matrix`
**AND** the user clicks `Light` in the `ThemeSwitcher`
**THEN** `<html>` has no theme class (light is the default)
**AND** `localStorage.theme === 'light'`
**AND** the red pill is visible
**AND** the previous-theme storage (`trinity:previousTheme`) is NOT consulted

### S6 — Persistence across reloads

**WHEN** the user has theme `matrix` selected
**AND** the user reloads the page
**THEN** `<html>` has `class="matrix"` before first paint (no flicker)
**AND** the blue pill is shown
**AND** no hydration warning is emitted

### S7 — System theme follows OS

**WHEN** the user has selected `System`
**AND** the OS toggles to `prefers-color-scheme: dark`
**THEN** `<html>` gains `class="dark"` without user action
**AND** the switcher still reflects `System` as selected (not `Dark`)

### S8 — Prefers-reduced-motion disables rain

**WHEN** the current theme is `matrix`
**AND** the rain toggle is enabled (`trinity:rainEnabled === 'true'`)
**AND** the user has `prefers-reduced-motion: reduce`
**THEN** the `MatrixRain` canvas does NOT mount
**AND** no `requestAnimationFrame` loop runs for rain
**AND** theme-change CSS transitions are suppressed (`transition: none` at root)

### S9 — Rain toggle off by default

**WHEN** the user enters Matrix for the first time
**AND** `trinity:rainEnabled` is absent from `localStorage`
**THEN** the `MatrixRain` canvas is NOT mounted
**AND** the rain toggle (next to the blue pill) is in the off state
**AND** clicking the rain toggle mounts the canvas and sets `trinity:rainEnabled === 'true'`

### S10 — Contrast compliance across all themes

**WHEN** the contrast test suite runs
**THEN** every `(foreground, background)` semantic pair in `:root`, `.dark`, and `.matrix` meets WCAG AA (4.5:1 for `body`, 3:1 for `large` text and UI)
**AND** the test fails the build if any pair regresses below the threshold

### S11 — Token parity

**WHEN** the parity test runs
**THEN** every CSS variable defined in `:root` is also defined in `.dark` AND in `.matrix`
**AND** the test fails the build if any variable is missing from either block

### S12 — axe-core passes per theme

**WHEN** the E2E suite runs the theme cycle (light → dark → matrix → exit)
**THEN** axe-core reports zero violations of severity `serious` or higher for each theme
**AND** focus rings are visible on every interactive element under the Matrix palette

### S13 — Touch targets

**WHEN** rendered on a 375 px viewport
**THEN** the red pill, blue pill, and each `ThemeSwitcher` option have a minimum hit area of 44×44 px

### S14 — Screen reader announcements

**WHEN** a screen reader focuses the red pill
**THEN** it announces the localized label ("Switch to Matrix theme" / Spanish equivalent)
**WHEN** the red pill is activated
**THEN** a `role="status"` / `aria-live="polite"` region announces "Matrix theme activated"
**WHEN** the `ThemeSwitcher` value changes
**THEN** `aria-pressed` updates on the segmented options and the active label is announced

### S15 — Trinity storage reservation

**WHEN** the user enters Matrix mode
**THEN** the storage keys written are exactly `theme` (via `next-themes`) and `trinity:previousTheme` (via `trinity.ts`)
**AND** no other `trinity:*` keys are written unless explicitly listed in this spec (e.g., `trinity:rainEnabled`)
**AND** no network request is made as a side effect of theme changes

## Out of scope (negative scenarios)

- Syncing the theme choice to the backend
- Auto-detecting a user's preferred theme from an external profile
- Per-workspace or per-project theme overrides
- Custom palette editor
- Wiring the helper module to any real `trinity` remote endpoint

## Non-functional

- **Performance**: Theme switch must not cause a layout shift > 0.1 CLS and must complete in ≤ 100 ms
- **Accessibility**: WCAG AA body contrast across all 3 themes; keyboard parity for switcher and pills
- **i18n**: All user-visible strings go through `locales/{es,en}/theme.json`; no hard-coded literals
- **Bundle**: CSS additions ≤ 2 KB gzipped; `MatrixRain` code-split and lazy-loaded when Matrix is active
- **SSR**: No hydration mismatch warnings; first paint renders the stored theme

## Security considerations — Threat → Mitigation

| # | Threat | Mitigation |
|---|---|---|
| T1 | **localStorage poisoning**: an attacker with any prior XSS or a malicious browser extension writes `trinity:previousTheme = "<script>…"` or an invalid theme name. On read, the value flows into `setTheme(...)` and ultimately into `document.documentElement.className` | `trinity.getPreviousTheme()` validates against the allowlist `{'light', 'dark', 'matrix', 'system'}` and falls back to `'system'` on mismatch. No reflection into DOM without allowlist check |
| T2 | **Theme class injection**: a future code path calls `setTheme(untrusted)`; `next-themes` would apply the value as a CSS class on `<html>` | Only the `ThemeSwitcher`, `RedPill`, `BluePill` components call `setTheme`, each with compile-time-known literals. ESLint rule (follow-up) can forbid `setTheme(variable)` outside the theme module |
| T3 | **Clickjacking of the pill affordances**: an overlay frame tricks the user into toggling Matrix mode | Low severity (theme is non-privileged, non-destructive). Mitigation: the app already sends `X-Frame-Options: DENY` / `Content-Security-Policy: frame-ancestors 'none'` per EP-12; no extra work needed |
| T4 | **Rain-canvas CPU/battery abuse** on low-end devices degrades UX or drains battery silently | Rain capped at 30 fps; opt-in (off by default); respects `prefers-reduced-motion`; unmounts on theme exit; lazy-loaded so non-matrix sessions pay zero bundle cost |
| T5 | **Rain-canvas side-channel** (rendering arbitrary user content via canvas glyph pool) | Glyph pool is a hard-coded static array of katakana/digits in the component source; no interpolation from user input, URL, or storage |
| T6 | **Information disclosure via theme preference** (theme pref leaked to third parties) | Theme lives in same-origin localStorage; no cookie, no network traffic. Non-sensitive by nature; documented as such |
| T7 | **Hydration-time class mismatch** leaks prior-session theme on a shared device | Out of scope — same posture as existing `dark` mode. If a shared-device hardening epic ever lands, it covers this uniformly |

**Residual risks**: none above `low` severity. Theme is non-privileged UI state.
