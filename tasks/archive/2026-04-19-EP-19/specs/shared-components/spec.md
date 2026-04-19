# EP-19 · Capability 2 — Shared Domain Components

> **Addendum (Round-2 reviews, 2026-04-14)**:
> - **[A-M7]** `PlaintextReveal`: any response carrying the plaintext bypasses client-side caches (React Query, SWR, service worker). The component contract assumes the caller handles the network side; the component only guarantees no persistence **post-receipt**. Integration test mandatory: assert no plaintext copy in `performance.memory`, `DevTools/Application/Storage`, or any React Query cache after `onClose`.
> - **[L-M4]** `PlaintextReveal` screen-reader contract:
>   - `<input type="text" readOnly>` with **`aria-label="Clave de acceso, oculta"`** by default (masked). On reveal toggle, the label **swaps to `"Clave de acceso, visible"`** and focus moves to the **Copy** button (not the input) so the next SR announcement is "Copiar", never the plaintext. Document this in the component's a11y notes.
>   - Never announce the plaintext value through `aria-live`.
>   - The reveal toggle itself: `<button aria-label="Mostrar clave" aria-pressed={revealed}>`.
> - **[L-M3]** Every dialog component in the catalog has a mandatory `[T:a11y]` entry `test_<name>_returns_focus_to_trigger_on_close` — added to the uniform-API test checklist for dialog-kind components (`TypedConfirmDialog`, `CheckboxConfirmDialog`, `PlaintextReveal`, `CommandPalette`).
> - **[F-M2]** `CommandPalette` registry is **keyed by `pathname`**, not by component lifecycle. `useCommandPaletteRegistry(pathname, commands)` reads current pathname from `usePathname()` and stores commands under that key. On pathname change the previous key's commands are cleared. Multi-tab: scope registry to `document.hasFocus()` at dispatch time (commands from Tab B don't fire when Tab A has focus — see Should-fix S6 backlog for formal per-tab key).
> - **[F-M5]** `HumanError` disclosure of `correlation_id` + raw `code` is **gated** behind a runtime capability `developer_mode` (per-user preference, default off; toggle in user settings). Non-technical users see only the humanized message + "Reintentar" action. Developers/admins can enable disclosure to copy the correlation id.

## Scope

A catalog of domain-aware components consumed by every epic. Built on shadcn/ui primitives. Each component has a single source of truth, a Storybook story, accessibility coverage, and tests.

## In Scope (~25 components)

Organized by category:

**State & identity**
- `StateBadge` (draft/in_review/ready/blocked/archived/exported)
- `TypeBadge` (idea/bug/improvement/task/initiative/spike/change/requirement/milestone/story)
- `LevelBadge` (low/medium/high/ready)
- `SeverityBadge` (blocking/warning/info)
- `TierBadge` (inbox tier 1..4)
- `JiraBadge`, `LockBadge`, `VersionChip`, `RollupBadge`

**Tags & people**
- `TagChip`, `TagChipList` (with `+N` overflow)
- `OwnerAvatar`, `UserAvatar` (falls back to initials)

**Progress & metrics**
- `CompletenessBar` (aria-valuenow, level-colored)

**Confirmations**
- `TypedConfirmDialog` (user types expected string)
- `CheckboxConfirmDialog` (user ticks "Entiendo que no se puede deshacer")

**Critical UX moments**
- `PlaintextReveal` (token / credential reveal with all safety controls)
- `CopyButton` (clipboard + confirmation flash)

**Navigation & global**
- `CommandPalette` (⌘K, fuzzy search, recents, navigate)
- `ShortcutCheatSheet` (`?` opens it; per-page registry)
- `RelativeTime` (+ `<time datetime>`)

**Content**
- `DiffHunk` (added/removed/context styling)
- `HumanError` (error code → Spanish message with disclosure)
- `EmptyStateWithCTA` (thin wrapper over EP-12's `EmptyState` enforcing canonical CTA placement)

## Out of Scope

- Feature-specific components (they stay in their epic)
- Layout primitives owned by EP-12

## Scenarios — representative

(Full per-component scenarios live with each component's Storybook + test file. Below are the contract-level acceptance criteria that apply to the catalog.)

### Uniform API

- WHEN any badge or chip is rendered THEN it accepts `size?: 'sm' | 'md' | 'lg'`, `className?: string`, `'data-testid'?: string` at minimum
- WHEN a component has a variant prop (state, type, severity) THEN the allowlist is closed (TypeScript literal union); invalid values do not compile
- AND every component exports its props type alongside the component

### Accessibility

- AND every interactive component has visible focus (`ring-2 ring-ring ring-offset-2`)
- AND every icon-only button exposes `aria-label` (lint enforced)
- AND every announced state (badges with meaning) is read by screen readers as `Estado: <state>` / `Tipo: <type>` / `Severidad: <severity>`
- AND components respecting motion: `prefers-reduced-motion: reduce` disables internal animations

### `StateBadge`

- WHEN `<StateBadge state="ready" />` THEN shows localized label "Listo", semantic color `bg-state-ready`, check icon, sr-only `Estado: Listo`
- WHEN `state` is unknown (defensive) THEN renders a neutral `muted` variant with the raw string and logs a dev-console warning — does not crash

### `TypedConfirmDialog`

- WHEN `<TypedConfirmDialog expected="mi-clave" />` is open THEN submit is disabled until the user types the exact expected string
- WHEN the user types the expected string THEN submit becomes the only destructive-colored button on the screen
- AND focus is trapped; Escape closes (unless `preventDismiss: true`)
- AND the component is unopinionated about the action — it accepts `onConfirm` and parents compose

### `PlaintextReveal`

- WHEN rendered THEN the plaintext is masked by default (`••••…`) and revealed via an eye-toggle
- WHEN `minInteractionGate: true` (default) THEN the close button is disabled for 3 s AND until the user reveals / copies / downloads
- WHEN `autoClearMs` is set AND elapses THEN the component clears the plaintext from state, refs and DOM and emits `onAutoClear`
- WHEN closed THEN plaintext is purged synchronously before `onClose` fires; no value persists in React state after close
- AND the component MUST NOT write the plaintext to `localStorage`, `sessionStorage`, IndexedDB, cookies, the URL, or the console — asserted by integration test
- AND the download option produces a text file `{filename}.token` via `Blob` — no network call

### `CommandPalette`

- WHEN the user presses `⌘K` / `Ctrl+K` (Mac/Win) THEN the palette opens over the current page, focus moves inside
- WHEN the user types THEN results show: navigation targets (pages), recent items (last 10), search matches against work items and tags — debounced 150 ms
- WHEN the user presses `Enter` THEN the selected item's `onSelect` fires
- WHEN the user presses `Esc` THEN the palette closes and focus returns to where it was
- AND registered commands are contributed by each page via `useCommandPaletteRegistry`

### `ShortcutCheatSheet`

- WHEN the user presses `?` on any page THEN a sheet opens listing the shortcuts registered for that page (from `useKeyboardShortcut`), grouped by section
- AND shortcuts in form fields are suppressed (typing `?` in an input does NOT open the sheet)

### `HumanError`

- WHEN `<HumanError code="TOKEN_LIMIT_REACHED" />` is rendered THEN the localized message is shown; a "Detalles técnicos" disclosure reveals `code` and optional `correlation_id`
- WHEN `code` is unknown THEN the component falls back to `genericError` and logs to dev console

### `TagChip`

- WHEN `<TagChip tag={{name:"auth", color:"#6b21a8"}} />` THEN the background is `color` at 15% opacity and text is contrast-computed (white or black) via luminance
- AND the computation is cached per color value

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| `PlaintextReveal` leaking to persistence layers | Integration test snoops `localStorage`/`sessionStorage`/IndexedDB/cookies; any write fails the test |
| XSS in `HumanError` via error messages | All messages are static i18n keys; dynamic fields are rendered as text nodes, never HTML |
| Clipboard leakage via `CopyButton` | Clipboard write is user-initiated only; no programmatic write on mount |
| Command palette exposes cross-workspace suggestions | Registry is scoped to the current session; searches call scoped API endpoints (authz in service layer) |
| Icon package supply-chain risk | Pin `lucide-react` to a known version; Renovate PRs for bumps |

## Non-Functional Requirements

- Tree-shaken imports: each badge/component adds < 2 KB gzipped to the bundle it's used in
- Storybook renders each story in < 500 ms on CI
- axe-core zero `serious+` violations across every story
