# Frontend Review Round 2 — EP-18 & EP-19
**Date**: 2026-04-14
**Scope**: EP-19 (design system, tokens, shared components, i18n) + EP-18 frontend (MCP token UI)
**Reviewer**: frontend-developer agent
**Read-only. No code changed.**

---

## Must-Fix

### MF-1. EP-18 ships a local `PlaintextReveal.tsx` in `components/mcp-tokens/` — contradicts its own preamble
`EP-18/plan-frontend.md §6 file structure` lists `components/mcp-tokens/PlaintextReveal.tsx`. The preamble explicitly says "EP-18 does NOT re-implement any of this." This is a contradiction. If EP-19 is not complete when EP-18 ships, the file becomes permanent. Gate EP-18's plaintext flow on EP-19's component being merged, or the file will drift and both versions will be tested separately.
**Fix**: Remove `PlaintextReveal.tsx` from EP-18's file structure. Add hard dependency: EP-19 Phase B.5 must be merged before EP-18 §1.3 Step B begins. Enforce via import path only — no local copy allowed.

### MF-2. `useCommandPaletteRegistry` lifecycle is unspecified across App Router route changes
`EP-19/plan-frontend.md §2.2 CommandPalette` — registry populated via `useCommandPaletteRegistry(commands)` on mount, unregistered on unmount. In Next.js App Router, `layout.tsx` components do **not** remount on route changes; only `page.tsx` does. If the `CommandPalette` provider lives in layout (correct placement), and page components register commands on mount, the cleanup depends on page component unmount. But parallel routes and intercepting routes (used in any modal-route pattern) can keep the previous page mounted. Registry entries from the previous route will linger and show stale commands.
**Fix**: `EP-19/plan-frontend.md §2.2`: registry must key entries by `pathname` (from `usePathname()`), not by component lifecycle. On palette open, filter to current pathname's keys. Add integration test: navigate A→B→open palette→assert A's commands absent.

### MF-3. EP-18 re-tests `PlaintextReveal` behavior it delegates to EP-19
`EP-18/plan-frontend.md §1.3 Step B` lists 7 unit tests that duplicate EP-19's component contract (`test_step_b_close_button_disabled_for_3s`, `test_step_b_plaintext_auto_clears_after_5_minutes_idle`, etc.). These test EP-19's internals through EP-18's wiring layer — the tests will pass or fail based on EP-19's implementation, not EP-18's. When EP-19 changes the component, both test suites break.
**Fix**: EP-18 §1.3: keep only wiring tests (`test_step_b_correct_props_passed`, `test_step_b_onClose_callback_fires`). Delete the behavior tests — they live in EP-19. This is stated policy in the preamble but not followed in the task list.

### MF-4. Token parity CI check is described but not buildable as specified
`EP-19/specs/tokens-and-theming/spec.md` — "a CI check asserts parity" between `tailwind.config.ts` and `globals.css`. `EP-19/plan-frontend.md §1.1 step 2` says "Write parity test asserting every key in `tokens.ts` has both `:root` and `.dark` values." This is a unit test over a TS file, not a CI check over CSS variable presence in the compiled output. If `globals.css` defines a variable under `.dark` and `tokens.ts` types a matching key but the CSS var name has a typo, the test passes and dark mode is broken.
**Fix**: The parity test must parse the CSS file directly (regex or postcss AST), not just validate `tokens.ts` types. Clarify this in `EP-19/plan-frontend.md §1.1 step 2`.

### MF-5. `HumanError` correlation_id disclosure creates UX noise at scale
`EP-19/specs/shared-components/spec.md §HumanError` — every error renders a "Detalles técnicos" disclosure showing `code` and `correlation_id`. For non-technical users (PMs, stakeholders — majority of this product's users per `docs/ux-principles.md §1`), this disclosure adds noise and the correlation_id is meaningless without a support ticket. More critically, the `correlation_id` prop is optional — when absent, the disclosure section renders with only the code, leaking internal error naming to end users.
**Fix**: `EP-19/specs/shared-components/spec.md §HumanError`: disclosure renders only when `correlationId` is provided AND a feature flag `SHOW_ERROR_DETAILS` is on (default off for non-admin users). Admin users and users with `CONFIGURE_INTEGRATION` capability see it always.

---

## Should-Fix

### SF-1. `PlaintextReveal` UX is burdensome for the common case
`EP-19/plan-frontend.md §2.2 PlaintextReveal`: default `minInteractionGate: true`, `gateSeconds: 3`, `autoClearMs: 5 * 60 * 1000`. The 3-second disabled close button is aggressive when the user has already copied the token (interaction gate satisfied). The spec says close is disabled until `(revealed || copied || downloaded) && gateElapsed` — both conditions. After copy, the user must still wait out the timer. For a user who copies immediately, that 3s wait is confusing and feels like a bug.
**Recommendation**: Change the gate logic to `gateElapsed || (copied || downloaded)` — either the timer expires OR the user completed an interaction. The timer alone is a safety net for users who open-and-close without reading, not a mandatory delay for users who act. The `EP-19/plan-frontend.md §2.2` spec and `EP-19/specs/shared-components/spec.md §PlaintextReveal` need updating.

### SF-2. Custom typed i18n will break on runtime locale switching
`EP-19/design.md §3.4` — custom `t()` with `keyof`-typed argument. The EN stub is described as a "mirror" but is explicitly incomplete ("English values"). If locale switching is ever added, `t("some.key")` in EN context will return `undefined` for keys not yet in the EN dictionary. The type system only checks keys against the ES dictionary. The EN type is the same shape but TypeScript cannot verify runtime EN dictionary completeness at build time.
**Recommendation**: Add a CI test that asserts `Object.keys(flattenDict(es)).sort()` equals `Object.keys(flattenDict(en)).sort()` — key parity, not value completeness. `EP-19/plan-frontend.md §1.5` is missing this. Also note: `icuLite` with `plural/one/other` only covers Spanish well. English pluralization is identical at `one/other` but if any future language has 3+ plural forms (Polish, Russian), `icuLite` will silently fall through to `other`. Document this limitation in `EP-19/design.md §3.4`.

### SF-3. ESLint `tone-jargon` rule false-positive risk is high with current wordlist seed
`EP-19/tasks-frontend.md §A.3` wordlist includes "token" and "Ready" / "Draft". The word "token" appears in i18n key names (`mcp.*`), in code comments, in test descriptions, and in legitimate technical tooltips (the spec allows "token MCP" in tooltips). The `no-literal-user-strings` rule already covers JSX strings — `tone-jargon` would fire on dictionary values, which are the right place. But dictionary files live under `eslint-rules/` safelist's parent? The spec `EP-19/specs/copy-tone-i18n/spec.md §Tone linter` says the rule fires on dictionary entries — which means it will fire on the entry `"accessKey": "clave de acceso (token MCP)"` if "token" is in the wordlist.
**Recommendation**: `tone-jargon` must explicitly safelist dictionary files under `i18n/es/mcp.ts` for the "token" entry, or the MCP dictionary can't be authored. Document the safelist path in `EP-19/plan-frontend.md §1.5` and expand the lint test fixture to cover this exact case.

### SF-4. Size-limit 200 KB per route is unverifiable without route manifests
`EP-19/plan-frontend.md §A.1`, `docs/ux-principles.md §10` — 200 KB gzipped per route. `size-limit.config.js` must enumerate routes explicitly. EP-09 kanban page imports drag-drop logic + badge catalog + potentially a charting lib for completeness bars. EP-07 timeline page with diff hunks + version compare + comment anchoring. Neither epic's plan estimates their contribution to the 200 KB limit. The limit might be fine or impossible — it's not validated until Phase C migration is complete, at which point breaking it means rework across multiple epics.
**Recommendation**: Before Phase C begins, run `size-limit` against EP-09 and EP-07 pages in isolation with the EP-19 catalog loaded. If either exceeds 180 KB (leaving 20 KB headroom), address bundle splitting strategy proactively. This is a blocking pre-condition for Phase C, not a Phase D concern.

### SF-5. EP-18 i18n files are in `en/` but the source of truth is Spanish
`EP-18/plan-frontend.md §0.3` creates `apps/web/src/i18n/en/mcp-tokens.ts`. All strings are Spanish. The file path is `en/` (English). This is the inverse of EP-19's convention where `i18n/es/` is the source of truth. Either EP-18 was written before EP-19 landed the convention, or `en/` here is used as "the only file that exists so far." Either way, a developer running `t("mcp.issueTitle")` will look in `i18n/es/mcp.ts` (EP-19 convention) and find nothing — it's in `i18n/en/mcp-tokens.ts` instead.
**Fix**: `EP-18/plan-frontend.md §0.3`: rename to `apps/web/src/i18n/es/mcp.ts` (matching EP-19 structure). The EN stub goes in `i18n/en/mcp.ts` with placeholder values. Update the key structure to match `EP-19/specs/copy-tone-i18n/spec.md §mcp.*`.

### SF-6. Retrofit substitution table in `extensions.md#EP-19` is incomplete for hooks
`tasks/extensions.md §EP-19` component substitution table covers badge/dialog/reveal replacements. It does not cover hook migration: `useAutoSave` (EP-02), `useLock` (EP-17), `useRelativeTime` (EP-07 local) — each epic likely has its own implementation. EP-19 owns `useRelativeTime` and `useAutoClearPlaintext` but not `useAutoSave` or `useLock`. Phase C retrofit PRs will discover this and either duplicate the hooks or improvise.
**Recommendation**: `tasks/extensions.md §EP-19`: add a hooks subsection. Declare which hooks EP-19 owns (authoritative), which stay feature-local (EP-02's `useAutoSave`, EP-17's `useLock`), and which need extraction to a shared `hooks/` layer if more than one epic needs them. Decide before Phase C starts, not during.

---

## Nitpick

### NP-1. `EP-19/plan-frontend.md §2.2 RelativeTime` — `useSyncExternalStore` against a "1-Hz ticker" is a shared ticker, but where does the ticker live?
If every `<RelativeTime>` instance creates its own 1-Hz interval, 20 timestamps on a list page = 20 intervals. Specify that `useRelativeTime` subscribes to a singleton ticker (`src/lib/ticker.ts`) created once per app. `EP-19/plan-frontend.md §2.3`.

### NP-2. Storybook + Chromatic as "PoC during Phase B, decide GA post-catalog" defers a blocking decision
`EP-19/plan-frontend.md §7 open items` — visual regression via Chromatic is a PoC. Visual regressions on 25 components with dark mode + 3 sizes + interactive states are exactly the class of bugs Chromatic catches that axe-core does not. Deferring it means the catalog ships without a visual regression baseline. The cost of setting it up after-the-fact is higher than doing it at story authoring time.
**Recommendation**: Decide before Phase B (not after). If Chromatic is ruled out on cost, document why and what replaces it. "Decide later" is a gap, not a plan.

### NP-3. `EP-19/specs/shared-components/spec.md §Uniform API` — `'data-testid'?: string` on every component is fine, but missing `ref` forwarding
All system components built on Radix should forward refs for consumers that need imperative access (e.g., `<CommandPalette ref={paletteRef}>`). Not specifying this now means retrofitting `forwardRef` later when the first consumer needs it. Add `React.forwardRef` to the recipe in `EP-19/plan-frontend.md §2.1`.

### NP-4. EP-18 `§4.2` — `mcp-token-format.json` under `.well-known/` is a nice-to-have but exposes token format to scanners
`EP-18/plan-frontend.md §4.2`: "Detectable token regex published in `apps/web/public/.well-known/mcp-token-format.json` for client-side scanners (optional nice-to-have)." Publishing the regex for a secret token format under a public `.well-known/` path is a tradeoff. Legitimate use: secret scanning tools. Downside: also helps attackers pattern-match exfiltrated data. Decision belongs in a security review, not tagged as a "nice-to-have." Mark it as "requires security sign-off before shipping."

---

## Summary

| Severity | Count | Items |
|---|---|---|
| Must Fix | 5 | MF-1 through MF-5 |
| Should Fix | 6 | SF-1 through SF-6 |
| Nitpick | 4 | NP-1 through NP-4 |

**Top 3 blockers before implementation**:
1. **MF-1** — resolve the `PlaintextReveal` duplication before EP-18 starts Phase 1.3 Step B
2. **MF-2** — CommandPalette registry lifecycle is architecturally broken in App Router; fix before Phase B.6
3. **SF-5** — i18n file location mismatch will cause runtime failures the moment EP-18 and EP-19 are integrated
