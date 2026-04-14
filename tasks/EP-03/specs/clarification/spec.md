# US-030 — Guided Clarification & Gap Detection

## Summary

The system detects information gaps in work items and formulates targeted questions to help users produce complete, unambiguous elements. Gap detection runs rule-based first; LLM-enhanced analysis is triggered on demand or when rule-based confidence is low.

---

## Definitions

| Term | Definition |
|------|-----------|
| Gap | A missing or insufficiently specified field, section, or semantic attribute required for the element type |
| Clarification session | A turn-based exchange where the system asks questions and the user answers, linked to a specific element |
| Gap score | A numeric signal (0–1) representing completeness; derived at read time from rules + optional LLM assessment |
| Required field | A field that must be non-empty for the element type before transitioning out of `Draft` |
| Recommended field | A field that improves quality but does not block transition |

---

## Gap Detection — How It Works

### Rule-based layer (always runs, synchronous)

For each element type, a static schema defines required and recommended fields. The rule engine evaluates:

1. Empty or null required fields (hard gap)
2. Content below minimum length threshold per field (soft gap)
3. Missing acceptance criteria for User Story and Feature types (hard gap)
4. Missing `definition_of_done` for Task type (soft gap)
5. No linked parent for types that require hierarchy (e.g., Task must belong to a Story or Feature)
6. Contradictory state transitions (e.g., element marked `Ready` but gap score < threshold)

Each rule emits a `GapFinding` with: `field`, `severity` (hard | soft), `message`, `suggestion_hint`.

### LLM-enhanced layer (async, on demand)

Triggered when:
- User explicitly requests "review this element"
- Rule-based score is below 0.5 and element age > 30 minutes (background job)
- Element transitions to `In Review` state

The LLM receives the element content plus a structured prompt asking for semantic gaps (ambiguous acceptance criteria, undefined terms, missing risk considerations). Response is parsed into additional `GapFinding` records tagged `source=llm`.

LLM findings augment — never replace — rule-based findings. If LLM call fails, rule-based results are returned alone.

---

## Scenarios

### US-030-01 — System highlights gaps when element is opened

WHEN a user opens an element that has one or more hard gaps  
THEN the detail view displays a gap panel listing each finding with field name and message  
AND each hard gap is visually distinct from soft gaps  
AND the gap panel shows a completeness percentage (e.g., "60% complete")  
AND the panel is dismissible per session but re-appears on next load if gaps remain  

### US-030-02 — System formulates guided questions for hard gaps

WHEN a user opens the clarification assistant on an element  
THEN the system presents at most 3 prioritised questions based on the current hard gaps  
AND questions are phrased in plain language (not field names)  
AND each question references the specific section it addresses  
AND if there are no hard gaps, the system presents soft-gap questions instead  

### US-030-03 — User answers a clarification question

WHEN a user types an answer to a clarification question  
THEN the answer is stored as a message in the element's clarification thread  
AND the system re-evaluates gap findings and updates the completeness score  
AND if the answer resolves the gap, the corresponding finding is removed from the panel  
AND the system may ask a follow-up question if the answer is incomplete  

### US-030-04 — Iterative clarification loop

WHEN a user has answered a question and new gaps remain  
THEN the system presents the next prioritised question  
AND the user can answer, skip, or end the session at any time  
AND skipped questions are re-presented in the next session unless the gap is resolved  

### US-030-05 — LLM-enhanced review requested

WHEN a user explicitly triggers "AI review" on an element  
THEN the system runs the LLM-enhanced gap analysis asynchronously  
AND a loading indicator is shown during the call (max 10s timeout with graceful degradation)  
AND results are appended to existing findings once available  
AND LLM findings are labelled "AI suggestion" to distinguish them from rule-based findings  

### US-030-06 — Gap detection on state transition attempt

WHEN a user attempts to transition an element out of `Draft`  
AND the element has unresolved hard gaps  
THEN the transition is blocked  
AND the system shows exactly which hard gaps must be resolved  
AND the user can choose to resolve them inline or force-transition (owner only, with audit log entry)  

### US-030-07 — No gaps present

WHEN an element has no hard gaps  
THEN the gap panel is hidden  
AND the detail view shows a "complete" badge  
AND the clarification assistant is still accessible for soft-gap questions  

### US-030-08 — Gap detection for each element type

WHEN the element type is User Story  
THEN required fields are: title, description, acceptance_criteria, owner  
AND the system additionally checks that acceptance_criteria contains at least one WHEN/THEN pattern  

WHEN the element type is Feature  
THEN required fields are: title, objective, scope_in, scope_out, owner  

WHEN the element type is Task  
THEN required fields are: title, description, owner  
AND recommended fields include: definition_of_done, estimate  

WHEN the element type is Epic  
THEN required fields are: title, objective, business_value, owner  

---

## Out of Scope (US-030)

- Generating content to fill gaps (covered by US-032/US-033)
- Persistent chat threads (covered by US-031)
- Acceptance criteria generation (covered by definition assistance mode, US-033)
