# Spec — User Menu (F-7)

**Capability:** Consolidate user-scoped controls (theme, matrix, rain, settings, sign-out) into a single dropdown menu anchored to the avatar. Remove the ad-hoc theme toolbar from the sidebar.

## Context

Current state: `frontend/components/workspace/workspace-sidebar.tsx:91-98` renders a 4-control toolbar (`ThemeSwitcher`, `RedPill`, `BluePill`, `RainToggle`) squatting above the user footer. User footer separately exposes `Sign out` as an icon button. The arrangement is visually cramped and conceptually incoherent — theme controls have nothing to do with navigation.

## Scenarios

### Menu opens from avatar

- **WHEN** the user clicks the avatar in the sidebar footer
- **THEN** a dropdown menu opens anchored to the avatar
- **AND** the button sets `aria-expanded="true"` and `aria-haspopup="menu"`

### Menu contents

- **WHEN** the menu is open
- **THEN** it shows, in order: user identity block (name + email), divider, `Theme` subsection with segmented `Light` / `Dark` / `System` buttons, `Matrix mode` toggle row, `Rain effect` toggle row, divider, `Settings` (disabled with `Coming soon` tooltip), `Sign out`

### Theme segment mirrors current theme

- **WHEN** the menu opens with `dark` theme active
- **THEN** the `Dark` segment is visually selected (`aria-pressed="true"`)
- **AND** selecting `Light` applies the light theme and persists via `next-themes`

### Matrix toggle respects previous theme

- **WHEN** the user is in `dark` mode and toggles `Matrix mode` on
- **THEN** the theme becomes `matrix` and the toggle shows the blue-pill visual
- **WHEN** the user toggles `Matrix mode` off
- **THEN** the theme returns to `dark` (the previous non-matrix theme)

### Rain toggle gated on matrix

- **WHEN** Matrix mode is off
- **THEN** the `Rain effect` row is disabled and has `aria-disabled="true"` with a tooltip `Requires Matrix mode`
- **WHEN** Matrix mode is on AND the user toggles `Rain effect` on
- **THEN** the digital-rain canvas activates (reuses EP-20 component)

### Reduced-motion override

- **WHEN** the browser reports `prefers-reduced-motion: reduce`
- **THEN** the `Rain effect` row is disabled regardless of Matrix state
- **AND** the tooltip reads `Disabled by your system preference`

### Sign out preserved

- **WHEN** the user selects `Sign out`
- **THEN** the existing `logout()` flow runs (same as the current icon button)

### Old toolbar removed

- **WHEN** the new user menu ships
- **THEN** the sidebar no longer renders the standalone theme toolbar
- **AND** no component double-binds the theme controls

### Keyboard nav

- **WHEN** the menu is open AND the user presses `ArrowDown` / `ArrowUp`
- **THEN** focus moves between menu items
- **WHEN** the user presses `Esc`
- **THEN** the menu closes and focus returns to the avatar trigger
- **WHEN** the user presses `Enter` on a focused item
- **THEN** the item activates

### Outside click closes

- **WHEN** the menu is open AND the user clicks outside its bounds
- **THEN** the menu closes

### Mobile bottom-sheet

- **WHEN** the viewport width is < 768px
- **THEN** the menu renders as a bottom-sheet (or full-screen sheet) with at least 44px tap targets
- **AND** the sheet closes on swipe-down OR backdrop tap

### Accessibility

- **WHEN** axe-core runs against any workspace page
- **THEN** no violations are reported with the menu open or closed
- **AND** the menu is exposed with role `menu` and items with role `menuitem` / `menuitemradio` / `menuitemcheckbox` as appropriate

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| User menu leaks PII in DOM (email visible in screenshots) | Same identity already rendered in the sidebar footer — no new leak; the footer stays non-interactive |
| Focus trap broken → keyboard users stranded | Reuse an audited primitive (`@radix-ui/react-dropdown-menu` already used elsewhere in the codebase) |
| Theme persistence bypassed | Go through `next-themes` `setTheme()` — do not write to `localStorage` directly |
| `Settings` disabled placeholder misleads users | Visible `Coming soon` pill on the disabled row; never active, never routed |

## Out of Scope

- Real settings page wiring (a future EP-22 candidate)
- Per-workspace theme overrides
- User preference sync to backend (still localStorage-only per EP-20)
- Avatar image upload from the menu
