# EP-18 / EP-19 Accessibility Review — Round 2

**Scope:** EP-19 a11y gate + EP-18 frontend (MCP token flows). Read-only.
**Verdict:** Gate is structurally sound but under-specified in five places that will let regressions through CI. Fix before Phase A lands.

---

## Must Fix

### M1. Lighthouse sample is undersized and unscoped
`plan-frontend.md §4` samples 5 pages: `/`, `/workitems`, `/inbox`, `/admin/mcp-tokens`, `/settings/mcp-tokens`. Missing the audit surfaces this review explicitly cares about: `/admin/mcp-tokens/[id]/audit`, `/admin/audit`, and an auth-gated 403 page. No viewport split (desktop + 375 px mobile). No theme split (light + dark). No auth-state split (logged-out vs logged-in). Real a11y score diverges across these axes. Expand to: **{5 canonical pages} × {light, dark} × {1280, 375}** at minimum, and add the audit pages + 403 page to the canonical list.

### M2. "axe-playwright serious+" is not the right floor for a token reveal flow
`spec.md §a11y gate` blocks on `serious+`. Correct default, but `PlaintextReveal` and `TypedConfirmDialog` must block on `moderate+` too — a moderate violation in a destructive confirmation is a security-UX bug, not a nitpick. Tag these components (and any dialog) with a stricter axe rule set in the Playwright helper.

### M3. Focus-return contract is asserted only once, in prose
`spec.md` scenarios mention "focus returns to the element that opened the dialog; asserted by test" — but there is no corresponding `[T:a11y]` entry in `plan-frontend.md §2.1 Recipe` or in the `PlaintextReveal` / `TypedConfirmDialog` / `CommandPalette` / `ShortcutCheatSheet` test lists. Add explicit test: `test_<dialog>_returns_focus_to_trigger_on_close` for every dialog-like component. Radix gives you this for free via `<Dialog.Trigger>`; the test guards against someone bypassing Trigger with `setOpen(true)`.

### M4. `PlaintextReveal` screen-reader announcement is contradictory
`plan-frontend.md §1.5` (EP-18) says `input type="text"` + `readOnly` + `aria-label="MCP token, copy now"` so SR announces on reveal. EP-19 `spec.md §Security` says *"announces 'clave visible' but never announces the value through aria-live"*. These conflict: if it's `type="text"` (not masked at DOM level) and visible, SR WILL read the value on focus. The intent is right (don't pipe through `aria-live`), but the masked-by-default toggle must swap `aria-label` and `value` together — when masked, label says "Token oculto, pulsa para revelar"; when revealed, label says "Token visible, cópialo ahora". Also: when toggled to reveal, move focus deliberately to the Copy button, not the input — that way SR announces "Copy" instead of the plaintext value. Document this in the `PlaintextReveal` spec explicitly.

### M5. `?` shortcut form-field suppression is stated for `ShortcutCheatSheet` but not `⌘K`
`shared-components/spec.md` says `ShortcutCheatSheet` suppresses when focus is in a form field. `CommandPalette` scenarios do not. `⌘K` must also fire inside inputs (users expect palette to open from the search box). The plan-frontend hook `useKeyboardShortcut` says it "skips when focus in INPUT|TEXTAREA|SELECT|contentEditable" — that would break `⌘K`. Add an `options.allowInFormFields` flag (default false); `⌘K` opts in, `?` opts out. Test both paths.

### M6. Touch target ≥ 44×44 is not enforced — only documented
`a11y-and-performance/spec.md §Mobile floor` states the rule. `plan-frontend.md §1` lists lint rules `no-raw-tailwind-color`, `no-raw-text-size`, `no-literal-user-strings`, `tone-jargon` — no `min-touch-target` rule. Storybook addon-a11y won't catch this either. Add an ESLint rule or a Storybook interaction test that measures `getBoundingClientRect()` on every interactive role and fails on <44 px. Cheap win.

---

## Should Fix

### S1. `prefers-reduced-motion` coverage is asserted for "skeletons, toasts" but not palette/sheet/tooltip
`spec.md §Motion & sensory` lists skeleton + toast. The open/close of `CommandPalette`, `Sheet` (BottomSheet), `Tooltip` fade, and `Dialog` scale-in are all Radix defaults with transitions. `PlaintextReveal` toggle animation too. Add an explicit reduced-motion visual-regression story per component, or a single Storybook decorator test that flips the media query and snapshots.

### S2. Dark mode contrast — AA asserted, AAA aspiration unmeasured
`tokens-and-theming/spec.md` asserts parity (every token has dark value) but there is no **contrast** test — only a "has a value" test. Add a CI step that runs `wcag-contrast` against every semantic pair (`foreground` on `background`, `primary-foreground` on `primary`, etc.) in both themes and fails if AA fails. AAA-where-feasible stays aspirational; that's fine, but AA must be a contract.

### S3. SSE live regions — unspecified for EP-08 / EP-17 notifications
`tasks` under EP-12 mention `aria-live` in passing but the polite-vs-assertive choice is nowhere stated at the gate level. Rule: **polite** for notifications, inbox updates, audit-table row inserts; **assertive** only for revoke/rotate outcomes and token issuance. Add this to §8 of `ux-principles.md` and to `a11y-and-performance/spec.md` so downstream epics don't guess.

### S4. Per-page shortcut discoverability
`ShortcutCheatSheet` reads per-page registry. Nothing in the spec says the page must visibly advertise that `?` exists. First-time users won't press a key they don't know about. Add: every page renders a subtle keyboard-hint icon in the footer/header bound to `?` — and the `ShortcutCheatSheet` component has an auto-opens-once-per-session guard for new users.

### S5. `PerTokenAuditPage` sparkline has no AT fallback
`plan-frontend.md §2.1` and `tasks-frontend.md §2.4` describe the sparkline and mention "Error-code badges include text label". The sparkline itself is an SVG with no table fallback. AT users get nothing. Add a visually-hidden `<table>` (`sr-only`) rendering the same 24h bucketed data with `<caption>` describing the series, or a toggle "Ver como tabla" that swaps the SVG for the table. Tag the SVG `role="img"` with `aria-labelledby` pointing at a descriptive summary ("Invocaciones en las últimas 24h: pico de 42 a las 14:00, total 312").

### S6. `HumanError` disclosure — `aria-expanded` not in spec
`plan-frontend.md` says "Disclosure (`<Collapsible>`)". shadcn's Collapsible wires `aria-expanded` correctly, but the component's own test list (EP-19) doesn't assert it. Add `test_humanerror_disclosure_toggles_aria_expanded`. Same for the "Opciones avanzadas" section in `IssueTokenDialog` (EP-18 §1.3) — check that one too.

### S7. 3-second interaction gate — AT frustration risk
`PlaintextReveal` disables close for 3 s AND requires interaction. For a screen-reader user navigating the dialog, 3 s is fine; the interaction gate is the friction point. Confirm that **focus-landing** on the reveal toggle + pressing Enter counts as an interaction. It should, because `revealed` flips true on click/Enter. But test it explicitly: `test_plaintext_close_enables_after_keyboard_reveal`. Also: when the gate is active, the disabled close button must have `aria-describedby` pointing to a live text "Espera 2 s más…" so SR users understand why it's disabled, not just that it is.

### S8. Mobile card layouts at 375 px — no horizontal-scroll test
`tasks-frontend.md §3.3` (EP-18) has `test_responsive_card_layout_at_375px_viewport`. Good. But `a11y-and-performance/spec.md` says "no horizontal scroll on the page-level container" — not tested. Add a Playwright assertion on every canonical page at 375 px: `expect(scrollWidth === clientWidth)`.

### S9. Keyboard parity for `CommandPalette` navigation
`spec.md` lists ↑/↓ + Enter + Esc. Missing: Home/End (jump to first/last), PageUp/PageDown (category jump), Tab (should NOT exit the palette while open — focus trap). Radix Command handles arrow keys out of the box; verify Home/End and add a focus-trap assertion.

### S10. `CopyButton` success announcement
Flash for 2 s is visual. For SR, add `aria-live="polite"` region that reads "Copiado al portapapeles" once on success. Right now only the label swaps, which SR may or may not re-announce depending on whether it's treated as a live region.

---

## Nitpick

### N1. "AAA where feasible" is unmeasurable
Drop from spec or make it a specific list (e.g., "body text and primary CTA AAA in light theme"). Currently aspirational noise.

### N2. Reduced-motion — toast ≤200 ms contradicts "disable animations"
`spec.md` says toasts enter/exit ≤200 ms AND `prefers-reduced-motion` disables animations. Either `opacity: 0 → 1` with no transform, or instant swap. Clarify the reduced-motion branch: "no slide, no scale, opacity-only transition 100 ms OR instant".

### N3. `role="progressbar"` on `CompletenessBar`
Fine, but when `percent` is unknown/indeterminate, the spec is silent. Add: omit `aria-valuenow`, set `aria-busy="true"` — per ARIA APG.

### N4. `RelativeTime` re-render cadence
`plan-frontend.md §2.2` says "re-renders on interval (respects `prefers-reduced-motion`)". Interpretation: reduced-motion skips the live update? That's wrong — motion preference is about animation, not content change cadence. Drop the `prefers-reduced-motion` gate here; just rate-limit re-renders to once per minute for items older than 1h.

### N5. `StateBadge` triple-requirement (color + icon + text) stated generally
`shared-components/spec.md` says "colored status ALWAYS paired with an icon or text" — "or" is too loose. Canonical spec for this product should be "color + icon + text", not OR. Tighten the language.

### N6. Playwright `test_response_headers_include_cache_control_no_store`
Good test. Also assert `Pragma: no-cache` and `Vary: Cookie` on the `/admin/mcp-tokens` HTML response — some proxies ignore `Cache-Control` alone.

### N7. `ShortcutCheatSheet` — suggest a grouping contract
`useKeyboardShortcut` accepts `(combo, handler, options?)`. Add `options.group: 'Navegación' | 'Selección' | 'Acciones'` so the sheet renders grouped. Currently nothing ensures the sheet is scannable.

### N8. EP-18 `plan-frontend.md §4.1` duplicates EP-19 responsibilities
The entire "Accessibility" subsection (focus trap, ESC, focus return, aria-label, time datetime, contrast AA) is EP-19's gate, not EP-18's implementation. Delete; link to EP-19 spec. Reduces drift risk.

---

## Artifacts reviewed

- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/a11y-and-performance/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/shared-components/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/tokens-and-theming/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/plan-frontend.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/tasks-frontend.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/plan-frontend.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/tasks-frontend.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/docs/ux-principles.md` §8–9
