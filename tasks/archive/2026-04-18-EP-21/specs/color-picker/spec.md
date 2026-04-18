# Spec — Color Picker (F-9)

**Capability:** Reusable color picker component replacing plain hex text inputs. Used by tag create/edit (F-10) and any future color field.

## Context

Current state: `frontend/app/workspace/[slug]/admin/page.tsx:538-544` renders a plain `<Input placeholder="#3b82f6">` for tag color. Users have to know hex. UX is unacceptable.

## Scenarios

### Preset palette

- **WHEN** the user opens a form containing the `ColorPicker`
- **THEN** 12 preset swatches are shown, aligned with the design tokens (e.g. red, orange, amber, yellow, green, emerald, teal, cyan, blue, indigo, purple, pink — all mid-tone, accessible contrast)
- **AND** the current value (if any) highlights the matching swatch with a ring

### Swatch selection

- **WHEN** the user clicks a swatch
- **THEN** its hex value is stored in the form state
- **AND** the swatch shows a selected ring
- **AND** any previously selected swatch deselects

### Custom hex entry

- **WHEN** the user clicks the "Custom" option
- **THEN** an inline text input appears accepting hex input
- **AND** the input validates against `/^#[0-9a-fA-F]{6}$/`
- **AND** valid input updates the stored color live (debounced 150ms)
- **AND** invalid input shows a field-level error (see F-4 envelope)

### Keyboard navigation

- **WHEN** the palette has focus AND the user presses arrow keys
- **THEN** focus moves between swatches in a grid (left/right/up/down)
- **WHEN** the user presses Enter or Space
- **THEN** the focused swatch is selected
- **WHEN** the user presses Tab
- **THEN** focus moves to the Custom option or the next form field

### Accessibility

- **WHEN** axe-core runs on a form containing the picker
- **THEN** no violations are reported
- **AND** each swatch has `aria-label` with the human-readable color name (e.g. "Blue") and `aria-pressed` state
- **AND** the component has `role="radiogroup"` with `aria-label="Color"`

### Matrix theme

- **WHEN** the page is in Matrix theme
- **THEN** swatches retain their colors (they represent the stored value, independent of theme)
- **AND** the ring/selection indicator uses the Matrix accent color for contrast

### Clear value

- **WHEN** the user deselects all swatches AND clears the Custom input
- **THEN** the form stores `undefined` for the color
- **AND** consumers treat this as "no color" (current behavior — color is optional on tags)

### Reusable

- **WHEN** a new form needs a color field
- **THEN** the developer imports `<ColorPicker value={} onChange={} />` — no duplication

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| User submits XSS via the Custom hex input | Strict regex validation `^#[0-9a-fA-F]{6}$`; reject anything else client-side AND server-side |
| Component swatch list drifts from design tokens | Swatches defined as a constant importing from the token file; CI smoke test renders the picker and asserts count |
| Palette inaccessible on Matrix theme (green on green) | Selection ring uses accent-cyan in Matrix theme; contrast checked via axe-core across all 3 themes |

## Out of Scope

- Gradient or HSL picker (hex-only for MVP)
- Color history / recently-used
- Eyedropper API
- Alpha channel
