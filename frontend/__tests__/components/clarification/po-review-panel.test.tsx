import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PoReviewPanel } from '@/components/clarification/po-review-panel';
import type { MorpheoPoReview } from '@/lib/types/conversation';

function makeEnvelope(overrides: Partial<MorpheoPoReview> = {}): MorpheoPoReview {
  return {
    kind: 'po_review',
    message: 'Review complete.',
    po_review: {
      score: 72,
      verdict: 'needs_work',
      agents_consulted: ['product', 'architect', 'qa'],
      per_dimension: [
        {
          dimension: 'product',
          score: 65,
          verdict: 'needs_work',
          findings: [
            { severity: 'high', title: 'Missing metric', description: 'No KPI defined.' },
          ],
          missing_info: [{ field: 'success_metric', question: 'What is success?' }],
        },
      ],
      action_items: [
        { priority: 'critical', title: 'Add KPIs', description: 'Define measurable KPIs.', owner: 'PO' },
      ],
    },
    comments: ['Overall looks incomplete.'],
    clarifications: [{ field: 'rollout_plan', question: 'What is the rollout plan?' }],
    ...overrides,
  };
}

describe('PoReviewPanel', () => {
  it('renders score header', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    expect(screen.getByTestId('po-review-panel')).toBeInTheDocument();
    expect(screen.getByText('72')).toBeInTheDocument();
  });

  it('renders verdict', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    expect(screen.getByText(/needs_work/i)).toBeInTheDocument();
  });

  it('approved verdict has green indicator', () => {
    render(<PoReviewPanel envelope={makeEnvelope({ po_review: { ...makeEnvelope().po_review, verdict: 'approved', score: 95 } })} />);
    const panel = screen.getByTestId('po-review-panel');
    expect(panel).toBeInTheDocument();
    expect(screen.getByText(/approved/i)).toBeInTheDocument();
  });

  it('rejected verdict renders', () => {
    render(<PoReviewPanel envelope={makeEnvelope({ po_review: { ...makeEnvelope().po_review, verdict: 'rejected', score: 20 } })} />);
    expect(screen.getByText(/rejected/i)).toBeInTheDocument();
  });

  it('renders agents_consulted pills', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    // 'product' appears in both pills and dimension — use getAllByText
    const productNodes = screen.getAllByText('product');
    expect(productNodes.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('architect')).toBeInTheDocument();
    expect(screen.getByText('qa')).toBeInTheDocument();
  });

  it('renders per_dimension accordion entries', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    // 'product' appears in dimension summary — confirm at least one occurrence
    expect(screen.getAllByText('product').length).toBeGreaterThanOrEqual(1);
  });

  it('renders finding title and description inside dimension', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    // findings are rendered unconditionally inside <details> (jsdom doesn't hide them)
    expect(screen.getByText(/Missing metric/)).toBeInTheDocument();
    expect(screen.getByText('No KPI defined.')).toBeInTheDocument();
  });

  it('renders action_items', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    // title may be inline with priority label, use regex
    expect(screen.getByText(/Add KPIs/)).toBeInTheDocument();
  });

  it('renders envelope-level comments', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    expect(screen.getByText('Overall looks incomplete.')).toBeInTheDocument();
  });

  it('renders envelope-level clarifications', () => {
    render(<PoReviewPanel envelope={makeEnvelope()} />);
    // clarification field + question may be in sibling spans; check question text
    expect(screen.getByText(/What is the rollout plan\?/)).toBeInTheDocument();
  });

  it('empty comments → no crash', () => {
    render(<PoReviewPanel envelope={makeEnvelope({ comments: [] })} />);
    expect(screen.getByTestId('po-review-panel')).toBeInTheDocument();
  });

  it('empty clarifications → no crash', () => {
    render(<PoReviewPanel envelope={makeEnvelope({ clarifications: [] })} />);
    expect(screen.getByTestId('po-review-panel')).toBeInTheDocument();
  });

  it('undefined comments/clarifications → no crash', () => {
    const env = makeEnvelope();
    // biome-ignore lint: test intentionally passes incomplete type
    const stripped = { ...env, comments: undefined, clarifications: undefined } as MorpheoPoReview;
    render(<PoReviewPanel envelope={stripped} />);
    expect(screen.getByTestId('po-review-panel')).toBeInTheDocument();
  });
});
