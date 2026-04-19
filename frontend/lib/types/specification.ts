/**
 * EP-04 — Specification, completeness, gaps, and next-step types.
 *
 * Source of truth: backend controllers (specification_controller.py,
 * completeness_controller.py, next_step_controller.py).
 */

// ─── Section ──────────────────────────────────────────────────────────────────

export type GenerationSource = 'llm' | 'manual' | 'revert';

export type SectionType =
  | 'summary'
  | 'problem_statement'
  | 'steps_to_reproduce'
  | 'expected_behavior'
  | 'actual_behavior'
  | 'acceptance_criteria'
  | 'solution_description'
  | 'technical_notes'
  | 'business_justification'
  | 'scope'
  | 'out_of_scope'
  | 'dependencies'
  | 'risks'
  | 'mockups'
  | 'definition_of_done'
  | 'environment'
  | 'impact'
  | 'notes'
  | 'time_box'
  | 'output_definition'
  | 'hypothesis'
  | 'research_questions'
  | 'methodology'
  | 'stakeholders'
  | 'success_metrics'
  | 'constraints'
  | 'test_strategy'
  | 'rollback_plan'
  | 'technical_approach'
  | 'context'
  | 'objective'
  | 'breakdown';

export interface Section {
  id: string;
  work_item_id: string;
  section_type: SectionType | string;
  content: string;
  display_order: number;
  is_required: boolean;
  generation_source: GenerationSource;
  version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface SpecificationData {
  work_item_id: string;
  sections: Section[];
}

export interface SpecificationApiResponse {
  data: SpecificationData;
}

export interface SectionUpdateRequest {
  content: string;
}

export interface SectionUpdateResponse {
  data: Section;
}

export interface SectionVersion {
  id: string;
  section_id: string;
  work_item_id: string;
  section_type: string;
  content: string;
  version: number;
  generation_source: GenerationSource;
  revert_from_version: number | null;
  created_at: string;
  created_by: string;
}

// ─── Completeness ─────────────────────────────────────────────────────────────

export type CompletenessLevel = 'low' | 'medium' | 'high' | 'ready';

/**
 * Per-dimension result from GET /completeness.
 * NOTE: `score` is 0.0–1.0 float (dimension-level), NOT 0–100.
 * The overall `CompletenessReport.score` is 0–100 int.
 */
export interface CompletenessDimension {
  dimension: string;
  weight: number;
  applicable: boolean;
  filled: boolean;
  score: number;      // 0.0–1.0
  message: string | null;
}

export interface CompletenessReport {
  score: number;      // 0–100 int
  level: CompletenessLevel;
  dimensions: CompletenessDimension[];
  cached: boolean;
}

export interface CompletenessApiResponse {
  data: CompletenessReport;
}

// ─── Gaps ─────────────────────────────────────────────────────────────────────

export type GapSeverity = 'blocking' | 'warning' | 'info';

export interface GapItem {
  dimension: string;
  message: string;
  severity: GapSeverity;
}

/** GET /gaps → { data: GapItem[] } */
export interface GapsApiResponse {
  data: GapItem[];
}

// ─── Next Step ────────────────────────────────────────────────────────────────

export interface ValidatorSuggestion {
  role: string;
  reason: string;
  configured: boolean;
  setup_hint?: string;
}

export interface NextStepResult {
  next_step: string | null;
  message: string;
  blocking: boolean;
  gaps_referenced: string[];
  suggested_validators: ValidatorSuggestion[];
}

export interface NextStepApiResponse {
  data: NextStepResult;
}
