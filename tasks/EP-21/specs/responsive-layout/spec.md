# Spec — Responsive Layout Widths (F-1)

**Capability:** Reclaim horizontal space on wide monitors without breaking mobile.

## Scenarios

### Wide-monitor content width

- **WHEN** the viewport width is ≥ 1440px
- **AND** the user navigates to `/workspace/[slug]/items`, `/workspace/[slug]/items/[id]`, `/workspace/[slug]/admin`, or `/workspace/[slug]/teams`
- **THEN** the content container uses `max-w-screen-2xl` (1536px)
- **AND** horizontal padding is `4rem` on either side

### Form-shaped pages keep narrow cap

- **WHEN** the user navigates to `/workspace/[slug]/items/new` or `/workspace/[slug]/inbox`
- **THEN** the content container keeps `max-w-4xl` (56rem)
- **AND** rationale is documented in `design.md` (form readability > horizontal space)

### Mobile padding preserved

- **WHEN** the viewport width is < 768px
- **THEN** every workspace page uses `px-4` (1rem) horizontal padding
- **AND** no horizontal scrollbar appears at 375px, 768px, 1024px, 1440px, 1920px

### Tables and lists use full width

- **WHEN** the viewport is ≥ 1440px
- **AND** the items list is rendered
- **THEN** columns stretch to fill the expanded container (no artificial inner max-width)

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Long lines of text (description, comments) become unreadable at 1536px | Apply `max-w-prose` (65ch) to paragraph-heavy content regions inside the wider container |
| Visual regression on existing pages | Run Playwright screenshot diff at 3 breakpoints before merging |

## Out of Scope

- Dynamic column reordering or user-configurable layouts
- Sticky sidebars (separate EP)
