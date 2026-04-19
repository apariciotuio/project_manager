# US-032 & US-033 — Contextual Improvements & Quick Refinement Actions

## Summary

US-032: The AI proposes improvements to specific sections of an element. The user previews each suggestion, then accepts or rejects per section. Accepted sections are atomically patched and a new version is created.

US-033: The user triggers quick single-action refinements (rewrite, concretize, expand, translate to template) on any section without a full suggestion flow.

---

## Definitions

| Term | Definition |
|------|-----------|
| Suggestion | An AI-generated proposed replacement for one or more sections of an element |
| Section | A named, independently patchable field of a work item (e.g., `description`, `acceptance_criteria`, `scope_in`) |
| Suggestion set | A collection of per-section suggestions produced by a single LLM call |
| Partial apply | Accepting a subset of sections from a suggestion set; rejected sections remain unchanged |
| Preview | Side-by-side view of current content vs. proposed content for each section in a suggestion set |
| Quick action | A single-section, single-intent refinement triggered by the user with no preview step (can be undone) |
| Version | An immutable snapshot of the element's content created when any section is patched |

---

## US-032 — Contextual Improvements with Preview and Partial Apply

### US-032-01 — User requests improvement on element

WHEN a user clicks "Improve this element" from the element detail view  
THEN the system generates a suggestion set for the element asynchronously  
AND a loading indicator is shown (max 15s; if exceeded, an error with retry is shown)  
AND the suggestion set is scoped to sections that have content (empty sections are not suggested)  
AND each suggestion includes: `section`, `current_content`, `proposed_content`, `rationale`  

### US-032-02 — User previews suggestion set

WHEN a suggestion set is ready  
THEN the UI displays a preview panel with one card per section  
AND each card shows a diff between current and proposed content  
AND each card has Accept and Reject buttons  
AND all cards default to "pending" (neither accepted nor rejected)  
AND a "Apply selected" button is enabled only when at least one card is accepted  
AND a "Reject all" shortcut closes the preview without changes  

### US-032-03 — User accepts a subset of sections

WHEN a user accepts at least one section and clicks "Apply selected"  
THEN only the accepted sections are patched onto the element  
AND rejected sections remain with their current content  
AND pending sections (neither accepted nor rejected) also remain unchanged  
AND a new version is created containing the patch  
AND the version metadata records: which sections changed, suggestion_set_id, acting user  

### US-032-04 — New version created on partial apply

WHEN sections are patched via partial apply  
THEN a new version snapshot is created atomically  
AND the element's `updated_at` and `version_number` are incremented  
AND the previous version remains accessible via the history panel  
AND the diff view shows exactly which sections changed between versions  

### US-032-05 — User rejects all suggestions

WHEN a user clicks "Reject all" or closes the preview without accepting  
THEN no changes are made to the element  
AND the suggestion set is marked `rejected` in the database  
AND no new version is created  

### US-032-06 — Suggestion set expiry

WHEN a suggestion set has been open for more than 24 hours without action  
THEN it is marked `expired`  
AND the user is informed that the suggestion is outdated if they attempt to apply it  
AND the user can generate a new suggestion set  

### US-032-07 — Concurrent edit conflict

WHEN a user attempts to apply a suggestion set  
AND the element's current version has changed since the suggestion was generated  
THEN the system detects the conflict  
AND presents the user with options: discard suggestion, regenerate suggestion against current version, or view diff  
AND does not apply the stale suggestion silently  

### US-032-08 — Improvement request from element thread

WHEN a user sends a message in an element thread requesting an improvement (e.g., "improve the acceptance criteria")  
THEN the system generates a targeted suggestion set scoped to the mentioned section  
AND the suggestion is presented as a preview card inline in the thread  
AND the user can accept or reject from within the thread without navigating to the preview panel  

---

## US-033 — Quick Refinement Actions

### US-033-01 — User triggers a quick action on a section

WHEN a user selects a section in the element detail view and opens the quick action menu  
THEN the following actions are available (contextually filtered by section type):
  - Rewrite: rephrase for clarity, same meaning
  - Concretize: add specificity, remove vague language
  - Expand: add detail, examples, or missing elements
  - Shorten: reduce length without losing meaning
  - Generate acceptance criteria: produce WHEN/THEN/AND criteria from description (User Story only)

### US-033-02 — Quick action executes and applies

WHEN a user selects a quick action  
THEN the system calls the LLM asynchronously for that section only  
AND a loading indicator is shown inline (not a full-page block)  
AND the result replaces the section content immediately upon arrival  
AND an undo option is shown for 10 seconds after application  
AND the change is recorded as a new version with `action_type=quick_action`  

### US-033-03 — Quick action undo

WHEN a user clicks undo within the 10-second window  
THEN the section content reverts to the value before the quick action  
AND the version created by the quick action is marked `reverted`  
AND no additional version is created for the undo (the reverted version is the audit trail)  

### US-033-04 — Quick action on empty section

WHEN a user triggers a quick action on an empty section  
THEN only "Expand" and "Generate acceptance criteria" are available  
AND other actions are disabled with a tooltip explaining why  

### US-033-05 — Quick action failure

WHEN the LLM call for a quick action fails  
THEN the section content is unchanged  
AND an inline error is shown with a retry button  
AND no version is created  

### US-033-06 — Quick action in assisted review mode

WHEN the system is in "assisted review" interaction mode  
AND the user triggers a quick action  
THEN the action is available but the result is shown as a preview card (not auto-applied)  
AND the user must explicitly confirm before the content is patched  

---

## Interaction Mode Context

The four interaction modes affect how suggestions and quick actions are surfaced:

| Mode | Suggestion trigger | Apply behaviour |
|------|--------------------|----------------|
| General chat | User-initiated from chat | Preview card in thread |
| Contextual improvement | User-initiated from section | Full preview panel |
| Assisted review | System-initiated on review request | Preview required, no auto-apply |
| Definition assistance | System-initiated on gap detect | Inline suggestion chips |

---

## Out of Scope (US-032, US-033)

- Bulk improvement across multiple elements simultaneously
- AI-generated content without user-visible preview in assisted review mode
- Automatic application without user action (no silent patches ever)
- Suggestion history browsing beyond the current session (version history covers this)
