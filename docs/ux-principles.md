# UX Principles — Work Maturation Platform

The product is used by Product Managers, Tech Leads, Founders, Business stakeholders, QA, Team Leads, and Admins (see functional spec §1). These profiles have very different tech fluency. The interface must **disappear**: fast, obvious, friendly, non-intimidating. Never make the user feel they have to learn the tool before they can use it.

This document is the source of truth for how the frontend looks, feels, and behaves. All frontend plans (EP-09, EP-18, future) reference it.

---

## 1. Ten principles

1. **Un camino por pantalla.** Each screen has **one** obvious primary action. Everything else is secondary or hidden behind a menu. If two actions are equally important, the design is wrong — go back and pick one.
2. **Revelación progresiva.** Never show a field that 90% of users don't need. Put rarely-needed options under a collapsed "Avanzado" section. Defaults cover the common case.
3. **Español plano, sin jerga.** "Clave de acceso para agentes" before "MCP token". "Listo para ejecutar" before "Ready". Technical terms are allowed only where the user is already living in them (Jira key, Git SHA). When unavoidable, a short tooltip explains.
4. **Los defaults funcionan.** If a user accepts everything by default, the outcome must be correct. Defaults are product decisions, not placeholders.
5. **Feedback inmediato y tranquilo.** Toasts are brief (3–5 s) and informative, not celebratory. No modals when a toast suffices. Animations under 200 ms. Never a silent spinner — always a short label ("Guardando…", "Cargando revisiones…").
6. **Teclado primero.** Every mouse action has a keyboard equivalent. Visible shortcuts for power users (`?` opens shortcut cheat-sheet on every page). Tab order always logical.
7. **Mobile no es "después".** Inbox, notifications, revisions, and critical actions work on mobile. List pages use responsive cards below 768 px. Touch targets ≥ 44×44 px.
8. **Errores en humano.** No raw HTTP codes, no stack traces, no backend field names. "Este nombre ya lo tiene otra clave — prueba con otro." If technical detail is useful, put it in a "Detalles" disclosure.
9. **Sin ruido visual.** Neutral gray baseline. Color **only** for state (green = ok / amber = warning / red = error) and for the primary action on the screen. No decorative shadows, no gradients, no illustrations that don't inform.
10. **Densidad cómoda.** Base vertical rhythm `space-y-4` (16 px). Cards use `p-6`. Tables use `py-3` per row. Never apartment-block-apretado, never hangar-medio-vacío.

---

## 2. Design system

**Library**: **shadcn/ui** on top of Radix UI + Tailwind CSS.

Rationale:
- Radix primitives handle focus traps, ARIA, keyboard navigation correctly — accessibility out of the box
- Components live **in the repo**, not in `node_modules` — full customization, zero vendor lock-in
- Minimalist styles align with "sin ruido visual"
- Default target for Next.js + TS in 2026

Any component we need that shadcn doesn't ship: build it on Radix primitives first; write our own only when Radix has no primitive. No Material UI, no Chakra, no Mantine (too opinionated visually, too heavy).

### Installed components (initial set)

`button`, `dialog`, `dropdown-menu`, `input`, `label`, `select`, `textarea`, `toast`, `table`, `badge`, `tabs`, `sheet`, `tooltip`, `separator`, `skeleton`, `card`, `command` (⌘K menu), `popover`, `scroll-area`, `avatar`.

Add components as needed — don't install all of shadcn speculatively.

---

## 3. Color palette

Tailwind theme extension (`tailwind.config.ts`):

### Neutrals (95% of UI)

- `bg-background` → `zinc-50` light / `zinc-950` dark
- `bg-card` → `white` light / `zinc-900` dark
- `border` → `zinc-200` light / `zinc-800` dark
- `text-foreground` → `zinc-900` light / `zinc-50` dark
- `text-muted-foreground` → `zinc-500` light / `zinc-400` dark

### Action (primary only, sparse use)

- `bg-primary` → `zinc-900` light / `zinc-100` dark (yes, the primary is neutral — let the one colored accent live in state, not in CTAs)
- Optional brand accent `bg-accent` → single Tuio brand color (TBD with design); used **only** for the Tuio logo and for elements that represent Tuio as a brand, never for generic CTAs

### State (only for meaning, never decoration)

- `bg-success` text on `emerald-600` — Ready, saved, passed
- `bg-warning` text on `amber-600` — pending, divergence, override active
- `bg-destructive` text on `red-600` — failed, revoked, blocking error
- `bg-info` text on `blue-600` — neutral info, links, selection

**Rule**: if a UI element has no *state* meaning, it must be neutral. A "Create" button is neutral zinc, not blue. A "Save" button is neutral zinc. Only "Revoke" and "Delete" earn red.

### Forbidden

- Gradients
- Drop shadows beyond `shadow-sm`
- Decorative background images
- More than one accent color on a single screen
- Color-only state (always pair color with text label or icon — for a11y)

---

## 4. Typography

- Family: **Inter** (variable font, via `next/font/google`)
- Sizes (Tailwind):
  - Display: `text-3xl font-semibold` — only on page titles
  - H1: `text-2xl font-semibold`
  - H2: `text-xl font-semibold`
  - H3: `text-base font-semibold`
  - Body: `text-sm` (14 px) — yes, 14 is our body; it packs density without feeling cramped at standard viewing distance
  - Caption: `text-xs text-muted-foreground`
- Line-height: default Tailwind `leading-6` for body
- Max line length for reading blocks: `max-w-prose` (~65ch)
- Never use more than 2 font weights per screen (regular + semibold)

Code and identifiers: `font-mono text-xs bg-muted px-1 rounded` for inline; `<pre>` blocks use `text-xs leading-5`.

---

## 5. Spacing & layout

- Base unit: Tailwind default (4 px)
- Vertical rhythm between sections: `space-y-8`
- Vertical rhythm within a section: `space-y-4`
- Form field gap: `space-y-2` (label + input) then `space-y-4` between fields
- Card padding: `p-6`
- Page gutter: `px-6 lg:px-8`
- Max content width: `max-w-6xl mx-auto` for most pages; `max-w-3xl` for detail/forms
- Tables: `py-3` per row, sticky header
- Mobile (< 768 px): list views swap to cards with `space-y-3`

---

## 6. Interaction patterns

### Primary action

Always bottom-right on dialogs, top-right on list pages. Label is a **verb in infinitive** ("Crear", "Guardar", "Revocar"). Never "OK" or "Submit".

### Destructive confirmation

For anything that destroys user-visible state:

- Dialog with clear explanation of consequences
- **Typed confirmation** (user types the name/id) OR **explicit checkbox** "Entiendo que esto no se puede deshacer"
- Confirm button is the only red button on the screen, disabled until confirmation gesture completes

### Loading

- Skeletons on initial list loads (match the shape of what's coming)
- Inline spinner + label on mutation buttons ("Guardando…")
- Never a full-page spinner over content that was already visible

### Empty states

Every list has an empty state:
- One sentence explaining what would normally be here
- Primary CTA to create the first item (when action-creating possible)
- No cute illustrations unless they inform

### Toasts

- Success: auto-dismiss 3 s
- Info: auto-dismiss 5 s
- Warning: auto-dismiss 7 s with undo action if applicable
- Error: **never auto-dismiss**; user must acknowledge
- Max 3 on screen; newer pushes older to dismiss

### Forms

- Labels above inputs (not floating — screen readers handle them better)
- Required marker: `*` after label, muted color
- Helper text below input, `text-xs text-muted-foreground`
- Error text replaces helper text, `text-xs text-destructive`, with icon prefix
- Submit button disabled only when form is invalid + user has attempted submit (don't gate on first keystroke — too hostile)

### Keyboard shortcuts

Global:
- `?` — open shortcut cheat-sheet
- `⌘K` / `Ctrl+K` — command palette (search + navigate)
- `g i` — go to inbox
- `g h` — go to home
- `Esc` — close topmost dialog / sheet

Per-page shortcuts listed in the cheat-sheet, never more than 6 per page.

---

## 7. Tone of voice

- **Tuteo** in Spanish. "Tus claves", not "Sus claves".
- **Frases cortas.** Un verbo, un complemento. Si una frase pasa de 15 palabras, córtala.
- **Acción directa.** "Crear clave" > "Generación de una nueva clave de acceso".
- **Sin exclamaciones**, salvo error grave. El producto es serio, no eufórico.
- **Sin emojis en UI de producto**. (Los emojis en Slack/notificaciones externas son otra conversación.)
- **Nombres propios**: Dundun siempre en mayúscula inicial, Puppet siempre en mayúscula inicial, Tuio siempre en mayúscula inicial.

### Micro-copy canónico

| En vez de | Usa |
|---|---|
| "Submit" | "Guardar" / "Crear" / "Enviar a revisión" (según caso) |
| "OK" | La acción que corresponda |
| "Cancel" | "Cancelar" |
| "Delete" | "Eliminar" / "Borrar" |
| "Revoke" | "Revocar" |
| "Error occurred" | Descripción humana del error concreto |
| "Loading…" | "Cargando tus elementos…" (qué se carga) |
| "Success!" | "Clave creada" (qué pasó) |
| "Are you sure?" | Explica las consecuencias, no preguntes al vacío |

---

## 8. Accessibility (non-negotiable floor)

- Contraste WCAG AA en texto normal, AAA cuando posible
- Focus ring visible en **todo** elemento interactivo (`ring-2 ring-ring ring-offset-2`)
- `prefers-reduced-motion` respetado — animaciones desactivadas
- `aria-label` en botones icon-only
- `<time datetime>` para todas las fechas relativas
- Tablas con `<caption>` + `scope="col"`
- Lighthouse a11y ≥ 95 en todas las páginas (bloquea merge)
- axe-core automatizado en tests de integración
- Screen reader spot-check documentado en cada PR que toca UI nueva

---

## 9. Mobile

- Breakpoints: `sm 640`, `md 768`, `lg 1024`, `xl 1280`
- Below `md`: tables become card lists, side panels become bottom sheets, multi-column forms become single column
- Touch targets `≥ 44×44 px` (Tailwind `min-h-11 min-w-11`)
- No hover-only interactions — alternative always present
- Inbox, notifications, and destructive confirmations tested at 375 px (iPhone SE)

---

## 10. Performance budget (UX guarantee)

- LCP ≤ 2.5 s (p75, cable)
- INP ≤ 200 ms (p75)
- CLS ≤ 0.1
- Bundle per page ≤ 200 KB gzipped after route split
- Images via `next/image`, lazy by default, explicit width/height to prevent CLS
- Skeletons for perceived performance, not spinners

---

## 11. What to do when in doubt

1. Look at what the user is trying to accomplish. One thing, not three.
2. Remove a field. Remove a button. Remove a color.
3. Ask: would my mother understand this without asking? If no, rewrite the label.
4. Ask: can I do this with the keyboard? If no, add the shortcut.
5. Check on mobile. If it breaks, the desktop design was wrong.

Simplicity isn't an aesthetic choice. It's the feature.
