# EP-19 · Capability 4 — Accessibility & Performance Gates

> **Addendum (Round-2 reviews, 2026-04-14)**:
> - **[L-M1]** Lighthouse sample is **`{5 canonical pages + per-token-audit + 403 forbidden} × {light, dark} × {1280 px, 375 px}` = 28 reports** per PR. Any report < 95 blocks merge. (Previously: 5 pages, one viewport, one theme — insufficient.)
> - **[L-M2]** axe-playwright severity floor:
>   - **`moderate+` blocks** on: `*ConfirmDialog`, `PlaintextReveal`, force-ready/override dialogs, any admin destructive action. A moderate in a destructive confirm is a security bug.
>   - **`serious+` blocks** elsewhere (default).
> - **[L-M6]** 44×44 px touch-target enforcement:
>   - Storybook interaction test measures `getBoundingClientRect()` on every interactive element in every catalog component's stories; fails if `width < 44 || height < 44`.
>   - Complemented by an ESLint rule `min-touch-target` that flags class combinations known to produce < 44 px (e.g., `h-8` on a button without compensating padding). Safelist allowed with justification comment.
> - **[L-M5]** `useKeyboardShortcut` default **skips form fields**. Opt-in to fire inside form fields via `useKeyboardShortcut('Mod+K', handler, { allowInFormFields: true })`. `⌘K` MUST use this flag; `?` MUST NOT. Tested both ways.

## Scope

Establish and enforce the non-negotiable floor for accessibility (WCAG AA, keyboard parity, screen-reader support) and performance (Core Web Vitals, bundle budget). Gate PRs on these in CI.

## In Scope

- Lighthouse a11y score ≥ 95 on every page
- axe-core automated check in Playwright E2E (severity ≥ `serious` blocks)
- Contrast checker (AA text, AAA optional)
- Keyboard parity tests
- `prefers-reduced-motion` honored everywhere
- LCP/INP/CLS sampling on canary
- `size-limit` per Next.js route
- Visual regression (Storybook Chromatic) — deferred but scaffolded

## Out of Scope

- Feature-level performance tuning (lives in the feature)
- Server-side performance (backend EPs)

## Scenarios

### a11y gate

- WHEN any Playwright E2E test renders a page THEN it runs `axe-playwright` and fails on severity ≥ `serious`
- WHEN a PR changes `apps/web/` THEN a required CI check runs Lighthouse a11y on a sample of 5 pages and fails if any scores < 95
- WHEN `prefers-reduced-motion: reduce` is set THEN **all** EP-19 and EP-12 shared components disable internal animations; a visual test confirms
- WHEN a screen reader navigates a shared component THEN every actionable element is announced with a meaningful label (aria-label or visible text)
- AND colored status (badges, chips, bars) is ALWAYS paired with an icon or text — a color-blind user gets the meaning

### Keyboard parity

- WHEN a UI action can be performed with a mouse THEN it can be performed with a keyboard (documented shortcut or standard Tab + Enter)
- WHEN a dialog opens THEN focus is trapped until close; Escape closes unless the dialog is explicitly non-dismissible
- WHEN focus leaves an element THEN the focus ring is visible on the next interactive element
- AND a global "Show keyboard shortcuts" (`?`) opens the `ShortcutCheatSheet` from any page

### Performance budget

- WHEN a Next.js route's first-party JS bundle exceeds **200 KB gzipped** THEN the `size-limit` CI check fails
- WHEN LCP on the canary sample exceeds 2.5 s (p75) for a route THEN a PR comment posts a warning; two consecutive failing canaries block merge
- WHEN INP exceeds 200 ms (p75) THEN same alert policy
- WHEN CLS exceeds 0.1 THEN same alert policy
- AND every image rendered through `next/image` carries explicit `width`/`height` or `fill` (no CLS from missing dims)
- AND fonts use `font-display: swap` + Inter size-matching fallback

### Dark mode parity

- WHEN dark mode is active THEN every semantic token has a dark value (no undefined tokens at runtime)
- AND a visual regression check captures light and dark variants of Storybook stories

### Mobile floor

- WHEN any interactive element is rendered THEN its hit target is ≥ 44×44 px (`min-h-11 min-w-11` in Tailwind)
- WHEN a page is viewed at 375 px THEN no horizontal scroll on the page-level container
- WHEN touch gestures are supported (swipe-down on BottomSheet) THEN a non-touch alternative exists (Escape, close button)

### Motion & sensory

- WHEN a skeleton renders THEN its shimmer respects `prefers-reduced-motion`
- WHEN a toast enters/exits THEN the animation is ≤ 200 ms
- AND no auto-playing video/audio exists anywhere in the product UI

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Focus loss on dialog close leaves the user lost | Focus returns to the element that opened the dialog; asserted by test |
| Shortcut collision with browser / OS shortcuts | Only use combos not owned by the browser for critical paths; `Ctrl+K` is widely accepted |
| Screen-reader announcement of sensitive data | `PlaintextReveal` announces "clave visible" but never announces the value through aria-live |

## Non-Functional Requirements

- CI a11y suite completes in < 5 minutes
- Lighthouse sample run < 3 minutes
- size-limit check < 30 s per route
