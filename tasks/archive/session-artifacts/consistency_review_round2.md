# Cross-Epic Consistency Review — Round 2

**Date**: 2026-04-14
**Scope**: 20 epics (EP-00 through EP-19) after EP-18 (MCP Server) and EP-19 (Design System) were added and after Dundun + Puppet real OpenAPI contracts were integrated.
**Prior round**: `tasks/consistency_review.md` — 7 Must-fix, 10 Should-fix, 3 Nitpick (all actioned during the 13-epic pass).

---

## Methodology

Systematic scan against 12 concerns:

1. Dependency graph integrity
2. Dundun contract drift (sync / async-webhook contract; no read API; no WebSocket)
3. Puppet contract drift (category-based isolation; no HTML snippets; ingestion endpoints pending)
4. MCP token naming consistency (`mcp_tokens`, `mcp:read`, `mcp:issue`)
5. Design-system naming drift (local components vs EP-19 catalog)
6. Terminology drift (glossary §2, state names, Dundun/Puppet capitalization, `work_item` vs `workitem`)
7. Data model conflicts (shared tables defined twice)
8. Cross-epic references to non-existent artifacts
9. EP-19 retrofit table self-consistency
10. EP-18 internal consistency (auth schema, Dundun thread source, Puppet snippet generation)
11. Tracker coherence (story counts, phase pipeline)
12. Dates (absolute ISO-8601 only)

---

## Findings

### 🔴 Must-fix

| # | Area | Epics | Finding | Resolution applied |
|---|---|---|---|---|
| 1 | Puppet contract drift | EP-09, EP-13 (proposal/design/specs/tasks) + EP-07 (design) | `wm_<workspace_id>` tag-based isolation assumed throughout. Real Puppet OpenAPI (v0.1.1) provides both `categories` and `tags`; isolation cleanly belongs in `categories` via convention `tuio-wmp:ws:<workspace_id>:workitem|section|comment`. Entity facets (state/type/owner/team/archived, user-tag slugs) remain as `tags`. `Source` model returns plain text (no HTML snippets). Platform-ingestion endpoints upstream are **not yet implemented** — workspace content searches return empty until they ship. | **Superseding notice** added at the top of: `EP-13/proposal.md`, `EP-13/design.md`, `EP-09/design.md`, `EP-09/specs/search/spec.md`. Full authoritative definition lives in `EP-18/specs/read-tools-assistant-search-extras/spec.md#semantic-search` and `EP-18/plan-backend.md#4.2`. Line-level cleanup of `tasks-backend.md` step names is deferred to the implementation PR (the authoritative spec now points to the right contract). |
| 2 | Dependency graph integrity | EP-18 | `tasks/tasks.md` listed EP-19 as a dependency for EP-18, but `EP-18/proposal.md#Dependencies` did not. | EP-19 added to `EP-18/proposal.md#Dependencies` with a one-line description of its role (frontend catalog, i18n, a11y gate consumed by MCP admin UI). |

### 🟡 Should-fix

| # | Area | Epics | Finding | Resolution applied |
|---|---|---|---|---|
| 3 | EP-19 retrofit scope clarity | `tasks/extensions.md#EP-19` | "Applies to:" listed 18 epics without explicitly saying why EP-12 is absent; readers could interpret as "missed" rather than "exempt". | Rewrote the "Applies to:" line to lead with "every epic with frontend scope **except EP-12**" and reference the "Amendments NOT required" section right after. |

### ℹ️ Informational (no action required)

| # | Area | Epics | Finding |
|---|---|---|---|
| 4 | Stale local component names still in EP-01/EP-02/EP-05 `tasks-frontend.md` | EP-01, EP-02, EP-05 | Local `StateChip`, `DerivedStateBadge`, `TaskStatusBadge`, `BlockedBadge` definitions survive in the task checklists alongside the EP-19 adoption preamble. This is **expected**: the preamble says the retrofit removes them; the checklist line items will disappear in each epic's retrofit PR (per `tasks/extensions.md#EP-19` execution order). No action this round — tracked as Phase-C migration work. |
| 5 | User-stories-count table | `tasks/tasks.md` | Table exists and was recently updated to include EP-13..EP-19 with totals 126 / 110 Must / 16 Should. Counts are read from each epic's `proposal.md#User Stories` and marked as re-runnable. |
| 6 | EP-15 tag propagation vs EP-18 category split | EP-15/design.md | EP-15 propagates user tag slugs via Puppet's `tags` field (`tag_<slug>`) — **correct** and independent from the workspace-isolation change. Two namespaces (category = isolation, tags = facets including user tags) coexist cleanly. |

### ✅ Verified clean

- **Dependencies**: no circular. EP-19 correctly depends only on EP-12; all other frontend epics implicitly depend on EP-19 via the retrofit table.
- **Dundun**: every reference to `DundunClient` is consistent with HTTP sync + HTTP async-webhook-with-callback. No `HTTP+WS`, no ws://, no WebSocket. Platform correctly owns thread store (Dundun has no read API).
- **MCP token naming**: `mcp_tokens`, `mcp:read`, `mcp:issue`, token format `mcp_...` uniform across `proposal.md`, specs, `design.md`, `plan-backend.md`, and `tech_info.md`.
- **Terminology**: Dundun and Puppet always capitalized. "work item" (prose) vs `work_items` (schema) consistent. No "Draft"/"Borrador" mixing in a single audience (ES in UI strings per §3.17; EN in spec AC blocks).
- **Data model conflicts**: none — EP-14 / EP-16 extensions to `work_items` are additive (`parent_work_item_id`, `attachment_count`) and aligned with `tech_info.md`.
- **Cross-references**: every `see EP-X` reference resolves to an existing artifact. New sections §3.14..§3.17 in `descripcion_funcional.md` are cross-referenced correctly from EP-18 / EP-19.
- **EP-18 internals**: `mcp_tokens` schema matches across `tech_info.md`, `EP-18/design.md` §4, `EP-18/specs/auth-and-tokens/spec.md`, `EP-18/plan-backend.md` §1.1. Snippet generation documented as server-side (never from Puppet). Dundun threads documented as reading platform store.
- **Tracker coherence**: phase pipeline updated to 20 epics; EP-18 and EP-19 listed as COMPLETED at their respective phases.
- **Dates**: all ISO-8601 absolute (`2026-04-14`). No relative dates detected.

---

## Severity summary

| Severity | Count | Status |
|---|---|---|
| Must-fix | 2 | Both resolved this round |
| Should-fix | 1 | Resolved this round |
| Informational | 3 | No action required / tracked to Phase-C retrofit |

---

## Pre-implementation gates

The plan is now internally consistent across all 20 epics. Remaining gates before implementation begins:

1. **Specialist reviews (round 2)** on EP-18 and EP-19:
   - `sw-architect` on EP-18 design (MCP process boundary, SSE bridge, SDK maturity)
   - `code-reviewer` (security focus) on EP-18 capability 1 (auth tokens) and capability 4 (signed URLs)
   - `frontend` review on EP-19 design (component API, shadcn adoption strategy, i18n)
   - `a11y` audit on EP-19 component catalog acceptance criteria
2. **Puppet platform-ingestion endpoints** (external deliverable). Not a blocker for EP-18 ship; `semantic.search` is documented to return empty on workspace content until they land. Ship-blocker only if product wants day-1 workspace-content search in MCP.
3. **Implementation order**:
   - EP-19 Phase A (foundation) → Phase B (catalog)
   - EP-18 backend capability 1 (depends on EP-00 token extension) → capability 2 → capabilities 3+4 parallel → capability 5
   - Rolling Phase-C migrations (EP-18 → EP-17 → … → EP-00)

---

## Diff vs round 1

Round 1 produced schema/dependency fixes that all landed in the 13-epic pass. Round 2's focus was the post-EP-18/EP-19 integration and the real Dundun/Puppet contracts. No round-1 finding regressed.
