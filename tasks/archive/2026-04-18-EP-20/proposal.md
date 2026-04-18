# EP-20 — Theme System: Light / Dark / Matrix

## Business Need

The platform already ships neutral light/dark tokens through EP-19. Two things are still missing:

1. A **user-facing theme switcher** that cycles through `light` / `dark` / `system` (today's `ThemeToggle` is a binary light↔dark toggle — it ignores `system` and cannot represent a third theme).
2. A **branded aesthetic twist** — a Matrix-flavored theme (phosphor green on black, monospace, optional digital rain) exposed through a red-pill affordance. It is both an easter egg (nod to the maintainer's friend) and a forward hook to the planned **Trinity** endpoint the platform will integrate with later.

The Matrix theme is not a cosmetic gimmick: it exercises the token architecture (third palette → proves the abstraction holds) and gives us a low-risk testbed for non-standard theming before any future "dense" or "high-contrast" variants.

## Objectives

- Extend the theme palette from 2 to 3 themes: `light`, `dark`, `matrix` (+ `system` auto-resolution for the first two)
- Replace the binary toggle with a **segmented theme switcher** (`light` / `dark` / `system`) + a **red pill** button that switches to `matrix`
- In `matrix` mode, show a **blue pill** button that returns to the previously selected non-matrix theme
- Persist the preference across sessions (leveraging `next-themes` localStorage)
- Maintain **WCAG AA contrast** in all three themes; run axe-core across every theme in E2E
- Respect `prefers-reduced-motion` — no digital rain, no theme-change transitions when the user opts out
- Non-invasive retrofit: every existing component that already uses semantic tokens inherits Matrix for free

## Non-Goals

- **No backend persistence**. Preference stays in localStorage — server-synced preference is a later call
- **No per-workspace or per-project theme overrides** — global user setting only
- **No branding assets** (logos, marketing imagery) — only the application chrome
- **No dynamic theme builder** (users pick from 3, not a palette editor)
- **No coupling to the real Trinity endpoint** — the endpoint integration is a separate epic. This task only *names* the theming module `trinity.ts` as a forward nod; behavior is entirely local
- **No new accessibility gates beyond EP-19** — reuse the same axe-core + Lighthouse pipeline, extended to test each theme

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-220 | As a user, I can pick between Light, Dark, and System from a theme switcher in the header toolbar | Must |
| US-221 | As a user, I can click a red-pill button to switch to Matrix mode | Must |
| US-222 | As a user in Matrix mode, I can click a blue-pill button to return to my previous non-matrix theme | Must |
| US-223 | As a user, my theme choice persists across page reloads and sessions | Must |
| US-224 | As a user with `prefers-reduced-motion`, Matrix mode disables the digital rain background and all theme-transition animations | Must |
| US-225 | As a user with a screen reader, each theme control has a meaningful `aria-label` and announces the current theme via `aria-pressed` / `aria-current` | Must |
| US-226 | As a frontend engineer, every existing component that uses semantic tokens renders correctly in Matrix mode without manual override | Must |
| US-227 | As a maintainer, contrast parity (WCAG AA for body text, AAA for critical elements) is enforced by CI across all 3 themes | Must |
| US-228 | As a user, I can toggle the digital rain canvas on/off from a small control next to the blue pill (off by default) | Should |

## Acceptance Criteria

### Theme switcher

- WHEN the page first loads AND no stored preference THEN the theme resolves from `prefers-color-scheme` (`light` or `dark`) — Matrix never auto-applies
- WHEN the user selects `Light`, `Dark`, or `System` THEN the `html` element gets the corresponding `class` (or no class for `light`) and the choice is stored in `localStorage`
- WHEN the user clicks the red pill THEN `html` gets `class="matrix"`, the previous theme is remembered, and the red pill is replaced by the blue pill

### Matrix palette

- WHEN `html.matrix` is active THEN every semantic token resolves to the Matrix palette (phosphor green `#00FF41` on black background `#0B0F0B`, cyan accent, amber warnings)
- AND body font family switches to `ui-monospace` stack
- AND focus rings render in phosphor green with a subtle glow
- AND all state/severity/tier badges remain legible (no green-on-green collisions) — verified by a contrast test per token pair

### Red / Blue pill affordances

- WHEN rendered in non-matrix themes THEN only the red pill is visible; in Matrix mode only the blue pill is visible
- WHEN the red pill is clicked THEN the transition is instant (no blocking animation) and the previous theme is saved to `localStorage` under `trinity:previousTheme`
- WHEN the blue pill is clicked THEN the theme reverts to `trinity:previousTheme` (falling back to `system` if missing)
- AND both buttons have `aria-label="Red pill — switch to Matrix theme"` / `"Blue pill — exit Matrix theme"` (localized)
- AND both buttons meet the 44×44 px touch target requirement

### Motion & accessibility

- WHEN `prefers-reduced-motion: reduce` is set THEN no digital rain canvas mounts AND theme transitions set `transition: none` on the root
- AND axe-core (serious+) passes for each theme in Playwright E2E
- AND the contrast parity test (`theme-contrast.test.ts`) asserts WCAG AA minima for every semantic token pair across all 3 themes

### Digital rain (Should)

- WHEN Matrix mode is active AND the user enables the rain control AND `prefers-reduced-motion` is not set THEN a fullscreen-background `<canvas>` renders katakana-style glyphs at ≤30 fps with `opacity ≤ 0.12`
- AND the canvas sits in a `position: fixed; inset: 0; z-index: -1; pointer-events: none;` layer so it never interferes with focus or click handling
- AND the canvas is unmounted when Matrix mode exits or the rain toggle is turned off

## Technical Notes

### Theme registration

- Extend `ThemeProvider` in `app/providers.tsx` with `themes={['light', 'dark', 'matrix']}` and `value={{ light: 'light', dark: 'dark', matrix: 'matrix' }}`
- `next-themes` already handles `class`-attribute application — no custom hook needed for the switching itself
- Introduce `lib/theme/trinity.ts` exposing `getPreviousTheme()` / `setPreviousTheme()` / `enterMatrix()` / `exitMatrix()` — pure helpers that wrap `localStorage` + `setTheme`

### Token layer

- Add a third CSS block `.matrix { ... }` in `app/globals.css` mirroring every variable already defined for `:root` and `.dark`
- Add a parity test (`theme-token-parity.test.ts`) that reads the file and fails if Matrix is missing any token present in light/dark
- Proposed palette (HSL):
  - `--background: 120 20% 4%`
  - `--foreground: 135 100% 50%` (phosphor green `#00FF41`)
  - `--primary: 135 100% 50%`
  - `--destructive: 0 100% 55%`
  - `--warning: 45 100% 55%` (amber)
  - `--info: 180 100% 50%` (cyan)
  - `--success: 135 100% 50%`
  - `--muted: 135 30% 15%` / `--muted-foreground: 135 60% 60%`
  - `--border: 135 60% 20%`
  - Domain tokens (state/severity/tier/level) follow the same saturation shift
- Font family override inside `.matrix`: `body { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace; }`

### Components (new, under `components/system/`)

| Component | Responsibility |
|---|---|
| `ThemeSwitcher` | Replaces `ThemeToggle`. Segmented control: Light / Dark / System. Uses `useTheme` from `next-themes` |
| `RedPill` | Button. Visible in non-matrix themes. Calls `enterMatrix()` |
| `BluePill` | Button. Visible only in Matrix. Calls `exitMatrix()` |
| `MatrixRain` (opt-in) | `<canvas>` background. Mounts only when `theme === 'matrix'` AND rain toggle is on AND no reduced-motion |

`ThemeToggle` is kept for one release as a deprecated re-export pointing to `ThemeSwitcher`, then removed.

### i18n

- New keys under `locales/es/theme.json` and `locales/en/theme.json`:
  - `theme.switcher.light` / `.dark` / `.system`
  - `theme.redPill.label` / `theme.redPill.aria`
  - `theme.bluePill.label` / `theme.bluePill.aria`
  - `theme.rain.toggle`
- Tone: tuteo, direct verbs. ES source of truth per EP-19.

### Testing

- Unit: `ThemeSwitcher`, `RedPill`, `BluePill`, `trinity.ts` helpers (Vitest + RTL)
- Integration: theme persistence across route changes
- E2E (Playwright): switch through all 4 options, verify `html` class, verify localStorage key, run axe-core under each theme
- Visual: Storybook snapshot per theme for each component in the `system/` catalog (follow-up, not blocking)

### Performance

- Matrix tokens add ~1 KB to `globals.css` (acceptable)
- `MatrixRain` canvas: throttled to 30 fps, tears down on theme exit — smoke-test with `size-limit`; route impact should be zero when the user never enters Matrix

### Security

- Nothing new. Preference is non-sensitive and stored in localStorage. No SSR of theme-specific content that could leak.

## Dependencies

- **EP-19** (Design System): provides the semantic token architecture, `ThemeProvider` wiring, Storybook, axe-core pipeline. Hard dependency
- **EP-12**: nothing new required
- **Existing `ThemeToggle`** (`frontend/components/system/theme-toggle/theme-toggle.tsx`): replaced by `ThemeSwitcher`

## Complexity Assessment

**Low-Medium**. Purely frontend, no new infrastructure. Main effort is token discipline + a11y testing across three themes + the pill affordances. Digital rain is an optional nice-to-have that can slip to a follow-up.

**Estimate**: ~1.5 days of frontend work (tokens + switcher + pills + tests), +0.5 day if digital rain ships in scope.

## Risks

| Risk | Mitigation |
|---|---|
| Matrix tokens break contrast on existing components | Parity test + contrast-test suite runs in CI per token pair |
| Digital rain hurts performance on low-end devices | Off by default; capped at 30 fps; respects reduced-motion; unmounts when not active |
| Red pill button becomes clutter | Keep it small, icon-only, tooltip-labeled; in header toolbar next to `ThemeSwitcher` — one affordance, one spot |
| Users accidentally enter Matrix mode and can't exit | Blue pill is prominent inside Matrix mode; `ThemeSwitcher` still visible and also exits |
| SSR flicker when Matrix is the stored preference | `next-themes` already handles hydration via `suppressHydrationWarning` on `<html>`; same pattern as dark mode |
| Canonical nitpick: the red pill exits the Matrix in the film | We flip the cultural metaphor deliberately ("show me the code behind the world"); documented in the user-visible tooltip copy |

## Open Questions

1. **Ship digital rain in MVP or defer?** → Recommend **defer** (Should, not Must); the pill affordances + three-theme palette are the core
2. **Place red pill in header or floating corner?** → Recommend **header, next to `ThemeSwitcher`** — discoverability without clutter
3. **Keyboard shortcut for Matrix toggle?** → Recommend **no shortcut in MVP**. If requested later, `Ctrl+Shift+M` is available
4. **Should Trinity endpoint integration live in this epic?** → No. When/if Trinity ships, a new epic wires it. This epic only reserves the naming (`trinity.ts`) and provides the hook point

## Out of Scope

- Server-side persistence of theme preference
- Any Trinity endpoint integration
- Third-party theme packs / theme marketplace
- Dense / high-contrast / colorblind-optimized variants (future epics if demand arises)
