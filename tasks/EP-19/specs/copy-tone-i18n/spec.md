# EP-19 · Capability 3 — Copy, Tone of Voice, i18n Base

## Scope

Establish Spanish (ES-ES, tuteo) as the source-of-truth locale. Seed the i18n dictionary with the terms every epic needs (states, types, actions, errors, roles, generic). Ship a tone linter that forbids English UI strings, formal "usted", and jargon. Provide a typed `t()` getter and a humane error mapper.

## In Scope

- i18n runtime (custom typed getter — no framework bloat MVP)
- ES dictionary seeded for all cross-cutting domains
- EN stub dictionary for future
- Tone linter (ESLint rule) with a jargon wordlist
- `no-literal-user-strings` ESLint rule
- Humane error mapper (`HumanError` consumer)
- Pluralization helper (simple ICU-lite)

## Out of Scope

- Additional locales beyond ES-ES and EN stub (add when needed)
- Rich-text translations / CMS
- RTL support

## Scenarios

### Typed getter

- WHEN `t("workitem.state.ready")` is called THEN it returns `"Listo"`
- WHEN `t("workitem.state.unknown")` is called THEN the TypeScript compiler rejects at build time (key is not in the typed dictionary)
- WHEN `t("common.itemsCount", { n: 5 })` is called AND the entry is `"{n, plural, one {# elemento} other {# elementos}}"` THEN the resolver returns `"5 elementos"`
- AND all dictionary files live under `apps/web/src/i18n/es/` grouped by domain

### No literal user strings

- WHEN a JSX file contains `<button>Save</button>` in `apps/web/src/` (outside `components/ui/`) THEN the lint rule rejects with `no-literal-user-strings`
- WHEN the string is `<p aria-hidden="true">—</p>` (presentational) THEN the rule allows
- WHEN the string matches a safelist (loading dots, simple separators, unicode arrows) THEN the rule allows

### Tone linter

- WHEN a dictionary entry contains "submit" / "click here" / "Are you sure?" / formal "usted" / "Ready" (as an English UI term) / "token" (user-facing) THEN the tone linter rejects with a canonical replacement suggestion
- AND the jargon wordlist is maintained in `apps/web/eslint-rules/tone-jargon.json` and changes require product sign-off in the PR

### Error mapper

- WHEN an API response returns `{ error: { code: "TOKEN_LIMIT_REACHED", message, details } }` THEN the client looks up `t("errors.TOKEN_LIMIT_REACHED")` and renders the localized string via `<HumanError code="TOKEN_LIMIT_REACHED" />`
- WHEN `code` has no mapping THEN `t("errors.generic")` is used and the unknown code is reported to the observability pipeline as `unmapped_error_code`
- AND the humanized message never contains the raw code, HTTP status, or stack trace in the primary view — those belong to the disclosure

### Dictionary structure (seed content)

The seed covers every cross-cutting concept so no epic has to invent base terms:

- `common.actions.*` — `save`, `cancel`, `confirm`, `delete`, `archive`, `restore`, `edit`, `create`, `close`, `back`, `next`, `continue`, `retry`, `loadMore`, `search`, `copy`, `download`
- `common.state.*` — `loading`, `saving`, `saved`, `error`, `empty`, `loadingMore`, `noMore`
- `common.confirm.*` — `typeToConfirm`, `understandIrreversible`
- `workitem.type.*` — one per type (idea, bug, improvement, task, initiative, spike, change, requirement, milestone, story)
- `workitem.state.*` — draft, in_clarification, in_specification, in_breakdown, in_review, ready, blocked, archived, exported
- `workitem.field.*` — owner, created_by, created_at, updated_at, version, tags, attachments, parent, project, jira_key, completeness
- `validation.rule.*` — generic labels (stub; epics fill specifics)
- `review.decision.*` — approved, rejected, changes_requested
- `assistant.*` — `thinking`, `suggest`, `acceptAll`, `acceptSection`, `reject`, `regenerate`
- `attachment.*` — `uploading`, `uploaded`, `uploadFailed`, `maxSize`, `invalidType`, `deleting`
- `tag.*` — `createNew`, `archived`, `merged`, `noTags`
- `mcp.*` — `accessKey`, `createKey`, `rotateKey`, `revokeKey`, `keyList`, `keyDetails` — user-facing names use "clave de acceso", the technical term "token MCP" only appears in technical tooltips
- `lock.*` — `editing`, `requestUnlock`, `forceRelease`, `lockLost`
- `role.*` — owner, reviewer, author, admin, superadmin
- `errors.*` — a canonical set: `generic`, `network`, `unauthorized`, `forbidden`, `notFound`, `validation`, `rateLimited`, `upstreamUnavailable`, `timeout`, plus specific domain codes

## Security (Threat → Mitigation)

| Threat | Mitigation |
|---|---|
| XSS via user-supplied placeholders in translations | Placeholder values are escaped by default; the getter never interpolates HTML |
| Key enumeration revealing unreleased features | ES dictionary is public by design (bundle); no secrets in keys/values |
| Tone drift over time | Tone linter; periodic copy audit as part of release checklist |

## Non-Functional Requirements

- Dictionary lookup < 0.1 ms for typical keys (plain JS object)
- Dictionary bundle per domain split-loaded only when that domain's pages mount
- Lint rule runs in < 5 s on the full repo
