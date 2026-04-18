'use client';

import { useState, lazy, Suspense } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { WorkItemHeader } from '@/components/work-item/work-item-header';
import { JiraExportButton } from '@/components/work-item/jira-export-button';
import { WorkItemEditModal } from '@/components/work-item/work-item-edit-modal';
import { StateTransitionPanel } from '@/components/work-item/state-transition-panel';
import { OwnerPanel } from '@/components/work-item/owner-panel';
import { TransitionHistory } from '@/components/work-item/transition-history';
import { OwnershipHistory } from '@/components/work-item/ownership-history';
import { SpecificationSectionsEditor } from '@/components/work-item/specification-sections-editor';
import { CompletenessPanel } from '@/components/work-item/completeness-panel';
import { NextStepHint } from '@/components/work-item/next-step-hint';
import { TasksTab } from '@/components/work-item/tasks-tab';
import { AttachmentList } from '@/components/attachments/attachment-list';
import { AttachmentDropZone } from '@/components/attachments/attachment-drop-zone';
import { ReviewsTab } from '@/components/work-item/reviews-tab';
import { CommentsTab } from '@/components/work-item/comments-tab';
import { TimelineTab } from '@/components/work-item/timeline-tab';
import { ChildItemsTab } from '@/components/work-item/child-items-tab';
import { VersionHistoryPanel } from '@/components/work-item/version-history-panel';
import { DocPreviewPanel } from '@/components/docs/doc-preview-panel';
import { WorkItemDetailLayout } from '@/components/detail/work-item-detail-layout';
import { useWorkItem } from '@/hooks/work-item/use-work-item';
import { useVersions } from '@/hooks/work-item/use-versions';
import { useThread } from '@/hooks/work-item/use-thread';
import { useAuth } from '@/app/providers/auth-provider';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';
import { StickyActionBar } from '@/components/layout/sticky-action-bar';
import { Pencil } from 'lucide-react';
import type { WorkItemResponse } from '@/lib/types/work-item';

// Lazy-loaded to keep detail page initial load fast (EP-13 Group 4)
const RelatedDocsWidget = lazy(() =>
  import('@/components/docs/related-docs-widget').then((m) => ({ default: m.RelatedDocsWidget })),
);

interface WorkItemDetailPageProps {
  params: { slug: string; id: string };
}

export default function WorkItemDetailPage({
  params: { slug, id },
}: WorkItemDetailPageProps) {
  const { workItem, isLoading, error, refetch } = useWorkItem(id);
  const { versions } = useVersions(id);
  const { thread } = useThread(id);
  const { user } = useAuth();
  const [editOpen, setEditOpen] = useState(false);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);

  // Pick the latest version id — null while versions haven't loaded yet
  const latestVersionId = versions.length > 0 ? (versions[0]?.id ?? null) : null;
  const threadId = thread?.id ?? '';

  if (isLoading) {
    return (
      <div className="p-6 flex flex-col gap-4" aria-busy="true" aria-label="Cargando elemento">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-8 w-96" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-24" />
          </div>
        </div>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    if (isSessionExpired(error)) return null;
    return (
      <div className="p-6" role="alert" aria-live="assertive">
        <p className="text-destructive text-sm">
          Error al cargar el elemento: {error.message}
        </p>
      </div>
    );
  }

  if (!workItem) return null;

  // Owner or superadmin can edit / export
  // TODO: add workspace membership role check once /workspaces/members role is exposed in AuthUser
  const canEdit = user !== null && (user.id === workItem.owner_id || user.is_superadmin);
  const canExport = canEdit;

  function handleSaved(updated: WorkItemResponse) {
    setEditOpen(false);
    // Merge updated item locally via refetch (pessimistic — wait for server)
    void refetch();
    // Suppress unused-variable warning for `updated` until local merge is implemented
    void updated;
  }

  const contentPanel = (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      {canEdit && (
        <WorkItemEditModal
          open={editOpen}
          workItem={workItem}
          onClose={() => setEditOpen(false)}
          onSaved={handleSaved}
        />
      )}

      {/* Metadata accordion — collapsed on mobile, always visible on md+ */}
      <details
        data-testid="metadata-accordion"
        className="group border border-border rounded-md md:border-0"
        open
      >
        <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium md:hidden">
          Metadatos
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className="h-4 w-4 transition-transform group-open:rotate-180"
            aria-hidden="true"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </summary>
        <div className="grid gap-4 px-3 pb-3 pt-1 md:grid-cols-2 md:px-0 md:pb-0 md:pt-0">
          <StateTransitionPanel
            workItem={workItem}
            onTransition={() => void refetch()}
            canForceReady={canEdit}
          />
          <OwnerPanel
            workItem={workItem}
            canReassign={canEdit}
            onReassigned={() => void refetch()}
          />
        </div>
      </details>

      <Tabs defaultValue="especificacion">
        <TabsList aria-label="Secciones del elemento">
          <TabsTrigger value="especificacion">Especificación</TabsTrigger>
          <TabsTrigger value="tareas">Tareas</TabsTrigger>
          <TabsTrigger value="revisiones">Revisiones</TabsTrigger>
          <TabsTrigger value="comentarios">Comentarios</TabsTrigger>
          <TabsTrigger value="historial">Historial</TabsTrigger>
          {canEdit && <TabsTrigger value="versiones">Versiones</TabsTrigger>}
          <TabsTrigger value="subitems">Sub-items</TabsTrigger>
          {canEdit && <TabsTrigger value="auditoria">Auditoría</TabsTrigger>}
          <TabsTrigger value="adjuntos">Adjuntos</TabsTrigger>
        </TabsList>

        <TabsContent value="especificacion" className="mt-4">
          <div className="grid gap-6 md:grid-cols-3">
            <div className="md:col-span-2">
              <SpecificationSectionsEditor workItemId={id} canEdit={canEdit} />
            </div>
            <div className="flex flex-col gap-4">
              <CompletenessPanel workItemId={id} />
              <NextStepHint workItemId={id} />
              <Suspense fallback={<Skeleton className="h-24 w-full" />}>
                <RelatedDocsWidget
                  workItemId={id}
                  onDocPreview={(docId) => setPreviewDocId(docId)}
                />
              </Suspense>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="tareas" className="mt-4">
          <TasksTab workItemId={id} />
        </TabsContent>

        <TabsContent value="revisiones" className="mt-4">
          <ReviewsTab workItemId={id} versionId={latestVersionId} />
        </TabsContent>

        <TabsContent value="comentarios" className="mt-4">
          <CommentsTab workItemId={id} />
        </TabsContent>

        <TabsContent value="historial" className="mt-4">
          <TimelineTab workItemId={id} />
        </TabsContent>

        {canEdit && (
          <TabsContent value="versiones" className="mt-4">
            <VersionHistoryPanel workItemId={id} />
          </TabsContent>
        )}

        <TabsContent value="subitems" className="mt-4">
          <ChildItemsTab workItemId={id} slug={slug} />
        </TabsContent>

        {canEdit && (
          <TabsContent value="auditoria" className="mt-4">
            <div className="flex flex-col gap-6">
              <TransitionHistory workItemId={id} />
              <OwnershipHistory workItemId={id} />
            </div>
          </TabsContent>
        )}

        <TabsContent value="adjuntos" className="mt-4">
          <div className="flex flex-col gap-4">
            <AttachmentDropZone disabled={!canEdit} />
            <AttachmentList
              workItemId={id}
              canEdit={canEdit}
              currentUserId={user?.id ?? ''}
              isSuperadmin={user?.is_superadmin ?? false}
            />
          </div>
        </TabsContent>
      </Tabs>

      <DocPreviewPanel
        docId={previewDocId}
        isOpen={previewDocId !== null}
        onClose={() => setPreviewDocId(null)}
      />

      {/* Mobile sticky action bar — fixed at bottom on < md, inline on md+ */}
      {canEdit && (
        <StickyActionBar>
          <Button
            size="sm"
            variant="outline"
            aria-label="Editar elemento"
            onClick={() => setEditOpen(true)}
            className="w-full sm:w-auto"
          >
            <Pencil className="h-4 w-4 mr-1.5" />
            Editar
          </Button>
          <JiraExportButton
            workItemId={id}
            canExport={canExport}
            externalJiraKey={workItem.external_jira_key ?? null}
          />
        </StickyActionBar>
      )}
    </PageContainer>
  );

  return (
    <div data-testid="detail-page-wrapper" className="overflow-x-hidden h-full">
      {/* Header row: full width */}
      <div className="px-6 pt-6 pb-2">
        <WorkItemHeader workItem={workItem} slug={slug} />
      </div>

      <WorkItemDetailLayout workItemId={id} threadId={threadId}>
        {contentPanel}
      </WorkItemDetailLayout>
    </div>
  );
}
