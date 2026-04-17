'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { WorkItemHeader } from '@/components/work-item/work-item-header';
import { WorkItemEditModal } from '@/components/work-item/work-item-edit-modal';
import { StateTransitionPanel } from '@/components/work-item/state-transition-panel';
import { OwnerPanel } from '@/components/work-item/owner-panel';
import { TransitionHistory } from '@/components/work-item/transition-history';
import { OwnershipHistory } from '@/components/work-item/ownership-history';
import { SpecificationSectionsEditor } from '@/components/work-item/specification-sections-editor';
import { CompletenessPanel } from '@/components/work-item/completeness-panel';
import { NextStepHint } from '@/components/work-item/next-step-hint';
import { TasksTab } from '@/components/work-item/tasks-tab';
import { ReviewsTab } from '@/components/work-item/reviews-tab';
import { CommentsTab } from '@/components/work-item/comments-tab';
import { TimelineTab } from '@/components/work-item/timeline-tab';
import { ChildItemsTab } from '@/components/work-item/child-items-tab';
import { ClarificationTab } from '@/components/clarification/clarification-tab';
import { VersionHistoryPanel } from '@/components/work-item/version-history-panel';
import { useWorkItem } from '@/hooks/work-item/use-work-item';
import { useAuth } from '@/app/providers/auth-provider';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';
import { Pencil } from 'lucide-react';
import type { WorkItemResponse } from '@/lib/types/work-item';

interface WorkItemDetailPageProps {
  params: { slug: string; id: string };
}

export default function WorkItemDetailPage({
  params: { slug, id },
}: WorkItemDetailPageProps) {
  const { workItem, isLoading, error, refetch } = useWorkItem(id);
  const { user } = useAuth();
  const [editOpen, setEditOpen] = useState(false);

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

  // Owner or superadmin can edit
  // TODO: add workspace membership role check once /workspaces/members role is exposed in AuthUser
  const canEdit = user !== null && (user.id === workItem.owner_id || user.is_superadmin);

  function handleSaved(updated: WorkItemResponse) {
    setEditOpen(false);
    // Merge updated item locally via refetch (pessimistic — wait for server)
    void refetch();
    // Suppress unused-variable warning for `updated` until local merge is implemented
    void updated;
  }

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <WorkItemHeader workItem={workItem} slug={slug} />
        </div>
        {canEdit && (
          <Button
            size="sm"
            variant="outline"
            aria-label="Editar elemento"
            onClick={() => setEditOpen(true)}
            className="shrink-0 mt-1"
          >
            <Pencil className="h-4 w-4 mr-1.5" />
            Editar
          </Button>
        )}
      </div>

      {canEdit && (
        <WorkItemEditModal
          open={editOpen}
          workItem={workItem}
          onClose={() => setEditOpen(false)}
          onSaved={handleSaved}
        />
      )}

      <div className="grid gap-4 md:grid-cols-2">
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

      <Tabs defaultValue="especificacion">
        <TabsList aria-label="Secciones del elemento">
          <TabsTrigger value="especificacion">Especificación</TabsTrigger>
          <TabsTrigger value="clarificacion">Clarificación</TabsTrigger>
          <TabsTrigger value="tareas">Tareas</TabsTrigger>
          <TabsTrigger value="revisiones">Revisiones</TabsTrigger>
          <TabsTrigger value="comentarios">Comentarios</TabsTrigger>
          <TabsTrigger value="historial">Historial</TabsTrigger>
          {canEdit && <TabsTrigger value="versiones">Versiones</TabsTrigger>}
          <TabsTrigger value="subitems">Sub-items</TabsTrigger>
          {canEdit && <TabsTrigger value="auditoria">Auditoría</TabsTrigger>}
        </TabsList>

        <TabsContent value="especificacion" className="mt-4">
          <div className="grid gap-6 md:grid-cols-3">
            <div className="md:col-span-2">
              <SpecificationSectionsEditor workItemId={id} canEdit={canEdit} />
            </div>
            <div className="flex flex-col gap-4">
              <CompletenessPanel workItemId={id} />
              <NextStepHint workItemId={id} />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="clarificacion" className="mt-4">
          <ClarificationTab
            workItemId={id}
            workItemVersion={workItem.updated_at ? 1 : 1}
            canEdit={canEdit}
          />
        </TabsContent>

        <TabsContent value="tareas" className="mt-4">
          <TasksTab workItemId={id} />
        </TabsContent>

        <TabsContent value="revisiones" className="mt-4">
          <ReviewsTab workItemId={id} />
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
      </Tabs>
    </PageContainer>
  );
}
