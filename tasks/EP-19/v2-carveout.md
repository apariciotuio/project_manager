# EP-19 — v2 Carveout

**Closed as MVP-complete 2026-04-19.** 25 components + 6 hooks + Phase A/B/C core shipped and tested. The items below are intentionally punted.

## UI enhancements (no MVP consumer)

- **`CommandPalette` (`⌘K` / `Ctrl+K`)** — fuzzy search + recents + registry. Infrastructure already shipped (`useKeyboardShortcut` hook in B.6 + shadcn `Command`). Nothing in the current migration surface consumes it (`tasks-frontend.md` line 78).
- **`ShortcutCheatSheet` (`?` key)** — depends on `CommandPalette` (`tasks-frontend.md` line 79).
- **`useCommandPalette()`** — ships with `CommandPalette` (`tasks-frontend.md` line 96).
- **`DiffHunk`** — no consumer in EP-00..EP-18 migrations. EP-07's diff engine (post-MVP) will drive the need (`tasks-frontend.md` line 85).

## CI gates (v2 CI epic — aligned with EP-12 carveout)

- **Lighthouse a11y ≥ 95** — requires deployed environment (`tasks-frontend.md` line 114).
- **axe-playwright on E2E** — requires Playwright CI run (`tasks-frontend.md` line 115).
- **`size-limit` per route** — requires `next build` in CI (`tasks-frontend.md` line 116).
- **Storybook CI build** — story authoring + `storybook build` step deferred (`tasks-frontend.md` line 117).

---

MVP scope (tokens, layout primitives, typography, color system, 25 components, 6 hooks, dark-mode parity, ESLint rules, 171 unit tests green) shipped and in production.

Re-open under the v2 CI epic when we're ready to gate builds on perf/a11y/bundle-size, or when EP-07 drives `DiffHunk` demand.
