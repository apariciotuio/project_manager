# Spec — Matrix Entry Cascade (F-8)

**Capability:** One-shot cascading-glyphs animation that plays when the user switches INTO Matrix mode. Distinct from the ambient `RainToggle` (which loops while Matrix is active).

## Context

EP-20 already ships:
- `RainToggle` — user-controlled *ambient* rain that loops indefinitely
- Matrix theme + red/blue pill switch

What's missing: a **one-shot transition effect** tied to the act of entering Matrix. It's the "swallowing the red pill" moment — plays once, on the inbound switch, then stops. No user control needed (it's tied to the event, not a setting).

## Scenarios

### Triggered only on inbound Matrix switch

- **WHEN** the user toggles Matrix mode ON (red pill → blue pill) from the user menu
- **THEN** a full-viewport canvas overlay appears at `z-index: 9999`
- **AND** glyphs begin cascading immediately

### Not triggered when leaving Matrix

- **WHEN** the user toggles Matrix mode OFF
- **THEN** no cascade plays
- **AND** the theme reverts instantly to the previous non-matrix theme

### Not triggered on page load with Matrix already active

- **WHEN** the page loads AND `localStorage` theme is already `matrix`
- **THEN** no cascade plays
- **AND** the Matrix theme renders immediately

### Glyph set

- **WHEN** the cascade renders
- **THEN** glyphs are drawn from a pool of half-width katakana (U+FF66–U+FF9D) and digits 0–9
- **AND** glyphs render in the phosphor-green Matrix token color (`#00FF41`)
- **AND** font is the Matrix theme monospace stack

### Column layout

- **WHEN** the cascade runs
- **THEN** 10–15 vertical columns are spawned, evenly spaced across the viewport width
- **AND** each column has independent speed (varied ±30% around a base rate)
- **AND** each column stream is 8–20 glyphs long
- **AND** the lead glyph of each column is rendered brighter (`#AAFFAA`) for the classic "head" effect

### Duration & cleanup

- **WHEN** the cascade starts
- **THEN** total duration is ~1.2s (defined as a constant, not magic number inline)
- **AND** at the end, the canvas is removed from the DOM (not hidden)
- **AND** the Matrix theme is fully applied before the canvas unmounts

### Non-blocking

- **WHEN** the cascade is running
- **THEN** `pointer-events: none` is set on the canvas
- **AND** users can click/type underneath without perceived lag

### Reduced motion skip

- **WHEN** `window.matchMedia('(prefers-reduced-motion: reduce)').matches` is true
- **THEN** the cascade is skipped entirely
- **AND** the Matrix theme is applied instantly (same behavior as today)

### Abort on re-trigger

- **WHEN** the cascade is running AND the user triggers another theme change (e.g. toggles back to dark)
- **THEN** the animation aborts cleanly (canvas removed, RAF loop cancelled)
- **AND** the newly selected theme applies without residual state

### SSR safety

- **WHEN** the component renders during SSR
- **THEN** no browser-only API (`window`, `document`, `requestAnimationFrame`, `matchMedia`) is called
- **AND** the canvas only mounts after hydration

### Performance

- **WHEN** the cascade runs on a low-end device (simulated CPU 4× slowdown)
- **THEN** frame rate stays at or above 30 FPS
- **AND** the canvas uses `requestAnimationFrame`, not `setInterval`

## Implementation note (non-normative)

Can likely share the drawing primitive with EP-20's `MatrixRain` component — both draw falling glyphs on a `<canvas>`. The difference is lifecycle: cascade is a one-shot tied to a theme-change event, rain is a long-lived toggle. Refactor target: extract a shared `matrix-canvas.ts` drawing utility, parameterized by `mode: 'burst' | 'loop'`.

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Animation blocks the main thread on low-end devices | `requestAnimationFrame`, bounded column count, canvas (not DOM nodes per glyph), abort on visibility-change |
| Accessibility regression — flashing pattern triggers vestibular issues | Hard skip on `prefers-reduced-motion`; no strobe effect (glyphs fade, don't flash); total duration bounded to 1.2s |
| Z-index war with modals / toasts | Document the canvas z-index (`9999`) explicitly; if a modal is open during the animation, the canvas still sits above — acceptable because duration is short and `pointer-events: none` |
| XSS via glyph pool | Glyph pool is a hardcoded Unicode range — no user input, no interpolation |
| Memory leak from abandoned RAF loops | `cleanup` in `useEffect` cancels the RAF and removes the canvas on unmount |

## Out of Scope

- Sound effect on transition
- Trinity endpoint integration (EP-20 reserved `trinity.ts` naming; wiring is a separate future EP)
- Configurable cascade duration / color via user settings
- Cascade on the blue-pill exit transition
