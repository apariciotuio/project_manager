# EP-19 · Capability 1 — Design Tokens & Theming

> **Addendum (Round-2 reviews, 2026-04-14)**:
> - **[F-M4]** Token parity CI check **parses `globals.css` directly** — it does NOT rely on TypeScript type checks alone. Implementation: a Node script reads `apps/web/src/styles/globals.css`, extracts every CSS variable under `:root` and `.dark`, and asserts the key sets are identical AND match `apps/web/src/styles/tokens.ts` keys. A typo in a CSS variable name is detected; a missing dark value is detected; a TS-level miss that happens to compile is detected. Script runs in CI as `pnpm tokens:parity`.

## Scope

Install shadcn/ui on Radix. Define semantic design tokens (palette, typography, spacing) in Tailwind + CSS variables. Ship light + dark themes via `next-themes`. Enforce via CI lints that features never use raw Tailwind colors or raw sizes.

## In Scope

- shadcn CLI setup (`components.json`, `pnpm dlx shadcn@latest init`)
- `tailwind.config.ts` extended with semantic tokens
- `apps/web/src/styles/globals.css` — CSS variables for light + dark
- Inter typography via `next/font/google`
- Icon set: `lucide-react`
- Initial shadcn component install list
- Lint rules: `no-raw-tailwind-color`, `no-raw-text-size`

## Out of Scope

- Feature-specific tokens (e.g., kanban-column width) — those live in the feature
- Brand accent color (filled later by design; slot exists)
- Internationalization tokens (covered in Capability 3)

## Scenarios

### shadcn install

- WHEN a new component is needed AND exists in shadcn THEN it is installed with `pnpm dlx shadcn@latest add <name>` — CI fails if any file under `apps/web/src/components/ui/` is hand-authored rather than shadcn-generated
- WHEN shadcn generates a component THEN its theme references semantic tokens only (no hard-coded colors)
- WHEN `components.json` is committed THEN reviewers check that the Tailwind preset, RSC, and TSX paths match repo conventions

### Color tokens

- WHEN a developer writes `bg-blue-500` in any file under `apps/web/src/` **except** `components/ui/` THEN the lint rule `no-raw-tailwind-color` rejects the commit
- WHEN a developer imports the semantic class `bg-primary` THEN the color resolves to the current theme's primary
- WHEN a new semantic token is added THEN it lives in `tailwind.config.ts` AND `globals.css` (both layers); a CI check asserts parity
- WHEN dark mode is active (`html.dark`) THEN every semantic token resolves to its dark-palette value

### Domain tokens

- WHEN `bg-state-ready` / `bg-state-blocked` / `bg-severity-blocking` / `bg-tier-1` is used THEN it resolves to the canonical color for that domain concept
- WHEN a developer attempts to use `bg-state-custom` THEN the lint rule rejects; the domain-token allowlist is closed
- AND the mapping is codified in `docs/ux-principles.md` §3; changes require updating the doc AND the config in the same PR

### Typography

- WHEN a developer uses `text-display` / `text-h1` / `text-h2` / `text-body` / `text-caption` / `text-code` THEN size + weight + line-height come from semantic config
- WHEN a developer writes `text-3xl font-bold` in a JSX file **except** `components/ui/` or `components/system/` THEN the lint rule rejects
- AND Inter is loaded via `next/font/google` with `subsets: ['latin', 'latin-ext']` and `display: 'swap'`; no FOUT on re-renders

### Icons

- WHEN a component needs an icon THEN it imports from `lucide-react` (tree-shakable)
- AND importing from other icon libraries (`react-icons`, `@heroicons/react`) is forbidden by lint

### Theming

- WHEN a user toggles `<ThemeToggle>` THEN `next-themes` applies `html.dark` without FOUC, honoring system preference on first load
- AND the theme state is persisted in `localStorage` key `theme` with values `light | dark | system`
- AND SSR respects the cookie `theme` if set (no flash)

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| Inline style injection via token values | Tokens are hex literals, generated at build; runtime never interpolates user input into CSS |
| XSS via `dangerouslySetInnerHTML` in themed components | System components never use `dangerouslySetInnerHTML`; the one allowed case (snippet highlight) sanitizes via `bleach`-equivalent allowlist |
| Drift between light/dark leaking sensitive state visually | Parity test: every semantic token has both light + dark defined; CI asserts no key missing |

## Non-Functional Requirements

- First contentful paint under 1 s on staging
- CLS from font loading = 0 (font-display swap + size-matching fallback)
- CSS bundle ≤ 40 KB gzipped
