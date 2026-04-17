import Link from 'next/link';
import { TypeBadge } from '@/components/domain/type-badge';
import { StateBadge } from '@/components/domain/state-badge';
import { CompletenessBar } from '@/components/domain/completeness-bar';
import type { WorkItemResponse, WorkItemState, WorkItemType } from '@/lib/types/work-item';
import type { WorkitemState } from '@/components/domain/state-badge';
import type { WorkitemType } from '@/components/domain/type-badge';
import type { CompletenessLevel } from '@/components/domain/level-badge';

// ─── Mappings ─────────────────────────────────────────────────────────────────

const STATE_MAP: Partial<Record<WorkItemState, WorkitemState>> = {
  draft: 'draft',
  in_review: 'in-review',
  changes_requested: 'blocked',
  partially_validated: 'in-review',
  ready: 'ready',
  exported: 'exported',
  in_clarification: 'draft',
};

const TYPE_MAP: Partial<Record<WorkItemType, WorkitemType>> = {
  story: 'story',
  milestone: 'milestone',
  bug: 'bug',
  task: 'task',
  spike: 'spike',
  idea: 'idea',
  requirement: 'requirement',
  enhancement: 'change',
  initiative: 'epic',
  business_change: 'change',
};

function scoreToLevel(score: number): CompletenessLevel {
  if (score >= 80) return 'ready';
  if (score >= 60) return 'high';
  if (score >= 30) return 'medium';
  return 'low';
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface WorkItemCardProps {
  workItem: WorkItemResponse;
  slug: string;
  /** Pre-resolved owner display name. Pass from parent to avoid per-row fetches. */
  ownerDisplayName?: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function WorkItemCard({ workItem, slug, ownerDisplayName }: WorkItemCardProps) {
  const badgeState = STATE_MAP[workItem.state] ?? 'draft';
  const badgeType = TYPE_MAP[workItem.type];
  const level = scoreToLevel(workItem.completeness_score);

  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-border last:border-0 hover:bg-muted/50 transition-colors">
      {/* Title link */}
      <div className="flex-1 min-w-0">
        <Link
          href={`/workspace/${slug}/items/${workItem.id}`}
          className="font-medium text-foreground hover:text-primary truncate block"
        >
          {workItem.title}
        </Link>
      </div>

      {/* Type badge */}
      <div className="shrink-0">
        {badgeType ? (
          <TypeBadge type={badgeType} size="sm" />
        ) : (
          <span className="text-body-sm text-muted-foreground">{workItem.type}</span>
        )}
      </div>

      {/* State badge */}
      <div className="shrink-0">
        <StateBadge state={badgeState} size="sm" />
      </div>

      {/* Completeness bar */}
      <div className="w-28 shrink-0">
        <CompletenessBar level={level} percent={workItem.completeness_score} showLabel />
      </div>

      {/* Owner */}
      {ownerDisplayName && (
        <div
          data-testid="work-item-card-owner"
          className="shrink-0 text-body-sm text-muted-foreground"
        >
          {ownerDisplayName}
        </div>
      )}
    </div>
  );
}
