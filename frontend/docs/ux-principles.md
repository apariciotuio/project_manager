# UX Principles

## Themes & the Red-Pill Metaphor

The platform ships three themes: **Light**, **Dark**, and **Matrix**.

Light and Dark follow standard system-preference conventions. Matrix is an opt-in branded aesthetic (phosphor green on near-black, monospace font stack) inspired by the maintainer's codebase culture.

### The deliberate metaphor flip

In the film, the red pill exits the Matrix. In this application, the red pill **enters** it. This is intentional.

The UX mental model: "take the red pill → show me the code behind the world" (i.e., enter the developer aesthetic). The blue pill brings you back to the familiar, comfortable UI. This reversal is documented here so future contributors do not accidentally "fix" it.

### Controls

- **ThemeSwitcher**: segmented control (Light / Dark / System). System follows `prefers-color-scheme`.
- **RedPill**: visible when the active theme is not Matrix. Clicking it stores the current theme in `localStorage['trinity:previousTheme']` and activates Matrix.
- **BluePill**: visible only in Matrix mode. Clicking it restores `trinity:previousTheme` (defaults to `system` if missing).
- **RainToggle**: visible only in Matrix mode. Toggles the optional digital-rain canvas animation. Off by default. Unconditionally disabled when `prefers-reduced-motion: reduce` is set.

### Accessibility

- All controls meet WCAG AA contrast (≥ 4.5:1 for body text, ≥ 3:1 for UI components) across all three themes — enforced by `__tests__/theme-contrast.test.ts`.
- All buttons have explicit `aria-label` values and meet the 44×44 px minimum touch target.
- Theme changes are announced via an `aria-live="polite"` region (`#theme-announcer`).

### Storage

Preferences are stored in `localStorage` only (no backend sync). Key namespace: `trinity:*`.

| Key | Value |
|-----|-------|
| `theme` | `'light' \| 'dark' \| 'matrix' \| 'system'` (managed by `next-themes`) |
| `trinity:previousTheme` | Last non-matrix theme, used by BluePill to restore |
| `trinity:rainEnabled` | `'true' \| 'false'` (rain toggle state) |
