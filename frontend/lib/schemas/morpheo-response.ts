/**
 * EP-22 v2 — Defensive Zod schema for MorpheoResponse envelope.
 * BE has already validated; this re-validates at the FE boundary for safety.
 */
import { z } from 'zod';

const ClarificationItemSchema = z.object({
  field: z.string().max(128),
  question: z.string().max(500),
});

const MorpheoQuestionSchema = z.object({
  kind: z.literal('question'),
  message: z.string().max(2000),
  clarifications: z.array(ClarificationItemSchema).max(50).optional(),
});

const SuggestedSectionItemSchema = z.object({
  section_type: z.string().max(64).regex(/^[a-z_]+$/),
  proposed_content: z.string().max(20480),
  rationale: z.string().max(2048).optional(),
});

const MorpheoSectionSuggestionSchema = z.object({
  kind: z.literal('section_suggestion'),
  message: z.string().max(2000),
  suggested_sections: z.array(SuggestedSectionItemSchema).min(1).max(25),
  clarifications: z.array(ClarificationItemSchema).max(50).optional(),
});

const VerdictSchema = z.enum(['approved', 'needs_work', 'rejected']);
const SeveritySchema = z.enum(['low', 'medium', 'high', 'critical']);
const PrioritySchema = z.enum(['low', 'medium', 'high', 'critical']);

const FindingSchema = z.object({
  severity: SeveritySchema,
  title: z.string(),
  description: z.string(),
});

const DimensionSchema = z.object({
  dimension: z.string(),
  score: z.number().int().min(0).max(100),
  verdict: VerdictSchema,
  findings: z.array(FindingSchema).max(25),
  missing_info: z.array(ClarificationItemSchema).max(50),
});

const ActionItemSchema = z.object({
  priority: PrioritySchema,
  title: z.string(),
  description: z.string(),
  owner: z.string(),
});

const PoReviewBodySchema = z.object({
  score: z.number().int().min(0).max(100),
  verdict: VerdictSchema,
  agents_consulted: z.array(z.string()).max(16),
  per_dimension: z.array(DimensionSchema).max(16),
  action_items: z.array(ActionItemSchema).max(50),
});

const MorpheoPoReviewSchema = z.object({
  kind: z.literal('po_review'),
  message: z.string().max(2000),
  po_review: PoReviewBodySchema,
  comments: z.array(z.string()).max(100).optional(),
  clarifications: z.array(ClarificationItemSchema).max(50).optional(),
});

const MorpheoErrorSchema = z.object({
  kind: z.literal('error'),
  message: z.string().max(2000),
});

export const MorpheoResponseSchema = z.discriminatedUnion('kind', [
  MorpheoQuestionSchema,
  MorpheoSectionSuggestionSchema,
  MorpheoPoReviewSchema,
  MorpheoErrorSchema,
]);

export type MorpheoResponseParsed = z.infer<typeof MorpheoResponseSchema>;

/**
 * Parse a MorpheoResponse envelope from a raw string.
 * Returns the parsed value or null on failure.
 */
export function parseMorpheoEnvelope(raw: string): MorpheoResponseParsed | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    const result = MorpheoResponseSchema.safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}
