# EP-03 — Clarification, Conversation & Assisted Actions

## Business Need

Raw inputs need refinement. The system must help users land ambiguous ideas through guided questions, persistent conversations, and contextual improvement suggestions. This is the AI-assisted layer that detects gaps, proposes improvements, and lets users accept/reject changes granularly.

## Objectives

- Detect information gaps and formulate useful questions
- Maintain persistent conversation threads per element and globally
- Propose contextual improvements with preview before applying
- Support partial acceptance of suggestions (per section)
- Allow quick refinement actions (rewrite, concretize, expand)
- Preserve conversation history for later resumption

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-030 | Clarify via guided questions | Must |
| US-031 | Maintain persistent conversation per element and general | Must |
| US-032 | Propose contextual improvements with preview and partial apply | Must |
| US-033 | Execute quick refinement actions | Should |

## Acceptance Criteria

- WHEN a user opens an element with gaps THEN the system highlights missing information
- WHEN the system proposes questions THEN the user can answer iteratively
- WHEN the system suggests improvements THEN the user sees a preview before applying
- WHEN the user accepts partially THEN only selected sections change AND a new version is created
- WHEN the user leaves and returns THEN conversation context is fully preserved
- AND conversations are linked to specific elements
- AND general (non-element) conversations are also supported

## Technical Notes

- Conversation threads model (thread -> messages)
- AI/LLM integration for gap detection and suggestions (wrapped, not direct dependency)
- Suggestion model: proposed content, target section, status (pending/accepted/rejected)
- Versioned patches per section
- Four interaction modes: general chat, contextual improvement, assisted review, definition assistance

## Dependencies

- EP-02 (capture, element exists to clarify)

## Complexity Assessment

**High** — LLM integration, conversation persistence, partial patch application, and section-level suggestions are architecturally complex. This is the differentiating feature.

## Risks

- Low-quality AI suggestions erode trust
- Conversation context window limits
- Partial apply logic complexity (conflicts, ordering)
- Performance of AI calls on every interaction
