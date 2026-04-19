'use client';

/**
 * EP-23 F-2 — Dashboard lean.
 * Replaces filler stats with focused, actionable lists.
 */
import Link from 'next/link';
import { Plus, CheckSquare, GitPullRequest, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState } from '@/components/layout/empty-state';
import { WorkItemList } from '@/components/work-item/work-item-list';
import { useWorkItems } from '@/hooks/use-work-items';
import { useAuth } from '@/app/providers/auth-provider';
import type { WorkItemState } from '@/lib/types/work-item';

// States that mean "still in progress" — anything not terminal
const NON_TERMINAL_STATES: WorkItemState[] = [
  'draft',
  'in_clarification',
  'in_review',
  'changes_requested',
  'partially_validated',
];

const SECTION_CAP = 5;

interface DashboardPageProps {
  params: { slug: string };
}

interface DashboardSectionProps {
  testId: string;
  heading: string;
  icon: React.ReactNode;
  viewAllHref: string;
  children: React.ReactNode;
}

function DashboardSection({ testId, heading, icon, viewAllHref, children }: DashboardSectionProps) {
  return (
    <section data-testid={testId} className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <span className="text-muted-foreground" aria-hidden="true">{icon}</span>
          {heading}
        </h2>
        <Link
          href={viewAllHref}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-label={`View all — ${heading}`}
        >
          View all
        </Link>
      </div>
      {children}
    </section>
  );
}

export default function DashboardPage({ params }: DashboardPageProps) {
  const { slug } = params;
  const { user } = useAuth();
  const projectId = user?.workspace_id ?? null;

  // "Pending to finish" — owned by me, non-terminal
  const pendingFinish = useWorkItems(projectId, {
    mine: true,
    mine_type: 'owner',
    states: NON_TERMINAL_STATES,
    limit: SECTION_CAP,
    sort: '-updated_at',
  });

  // "Pending my review / accept" — assigned to me as reviewer
  const pendingReview = useWorkItems(projectId, {
    mine: true,
    mine_type: 'reviewer',
    limit: SECTION_CAP,
    sort: '-updated_at',
  });

  // "Recently created by me" — last 5 I created, newest first
  const recentlyCreated = useWorkItems(projectId, {
    mine: true,
    mine_type: 'creator',
    limit: SECTION_CAP,
    sort: '-created_at',
  });

  const newItemHref = `/workspace/${slug}/items/new`;
  const itemsHref = `/workspace/${slug}/items`;

  return (
    <PageContainer variant="wide" className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <h1 className="text-h2 font-semibold">Dashboard</h1>
        <Button asChild size="default">
          <Link href={newItemHref} aria-label="New item">
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            + New item
          </Link>
        </Button>
      </div>

      {/* Pending to finish */}
      <DashboardSection
        testId="section-pending-finish"
        heading="Pending to finish"
        icon={<CheckSquare className="h-4 w-4" />}
        viewAllHref={`${itemsHref}?mine=true&mine_type=owner`}
      >
        <WorkItemList
          items={pendingFinish.items.slice(0, SECTION_CAP)}
          slug={slug}
          isLoading={pendingFinish.isLoading}
          error={pendingFinish.error}
          onRetry={pendingFinish.refetch}
          emptyState={
            <EmptyState
              variant="custom"
              heading="Nothing pending — you're on track"
              body="All your items are done or not yet started."
              cta={
                <Button asChild variant="outline" size="sm">
                  <Link href={newItemHref}>Create an item</Link>
                </Button>
              }
            />
          }
        />
      </DashboardSection>

      {/* Pending my review */}
      <DashboardSection
        testId="section-pending-review"
        heading="Pending my review / accept"
        icon={<GitPullRequest className="h-4 w-4" />}
        viewAllHref={`${itemsHref}?mine=true&mine_type=reviewer`}
      >
        <WorkItemList
          items={pendingReview.items.slice(0, SECTION_CAP)}
          slug={slug}
          isLoading={pendingReview.isLoading}
          error={pendingReview.error}
          onRetry={pendingReview.refetch}
          emptyState={
            <EmptyState
              variant="custom"
              heading="No pending reviews"
              body="You have no items waiting for your review."
              cta={
                <Link
                  href={itemsHref}
                  className="text-sm underline text-muted-foreground hover:text-foreground"
                >
                  Browse all items
                </Link>
              }
            />
          }
        />
      </DashboardSection>

      {/* Recently created */}
      <DashboardSection
        testId="section-recently-created"
        heading="Recently created by me"
        icon={<Clock className="h-4 w-4" />}
        viewAllHref={`${itemsHref}?mine=true&mine_type=creator`}
      >
        <WorkItemList
          items={recentlyCreated.items.slice(0, SECTION_CAP)}
          slug={slug}
          isLoading={recentlyCreated.isLoading}
          error={recentlyCreated.error}
          onRetry={recentlyCreated.refetch}
          emptyState={
            <EmptyState
              variant="custom"
              heading="No items created yet"
              body="Start by creating your first item."
              cta={
                <Button asChild variant="outline" size="sm">
                  <Link href={newItemHref}>Create an item</Link>
                </Button>
              }
            />
          }
        />
      </DashboardSection>
    </PageContainer>
  );
}
