'use client';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { WorkItemHeader } from '@/components/work-item/work-item-header';
import { SpecificationTab } from '@/components/work-item/specification-tab';
import { TasksTab } from '@/components/work-item/tasks-tab';
import { ReviewsTab } from '@/components/work-item/reviews-tab';
import { CommentsTab } from '@/components/work-item/comments-tab';
import { TimelineTab } from '@/components/work-item/timeline-tab';
import { ChildItemsTab } from '@/components/work-item/child-items-tab';
import { useWorkItem } from '@/hooks/work-item/use-work-item';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';

interface WorkItemDetailPageProps {
  params: { slug: string; id: string };
}

export default function WorkItemDetailPage({
  params: { slug, id },
}: WorkItemDetailPageProps) {
  const { workItem, isLoading, error } = useWorkItem(id);

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

  return (
    <PageContainer variant="wide" className="flex flex-col gap-6">
      <WorkItemHeader workItem={workItem} slug={slug} />

      <Tabs defaultValue="especificacion">
        <TabsList aria-label="Secciones del elemento">
          <TabsTrigger value="especificacion">Especificación</TabsTrigger>
          <TabsTrigger value="tareas">Tareas</TabsTrigger>
          <TabsTrigger value="revisiones">Revisiones</TabsTrigger>
          <TabsTrigger value="comentarios">Comentarios</TabsTrigger>
          <TabsTrigger value="historial">Historial</TabsTrigger>
          <TabsTrigger value="subitems">Sub-items</TabsTrigger>
        </TabsList>

        <TabsContent value="especificacion" className="mt-4">
          <SpecificationTab workItemId={id} />
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

        <TabsContent value="subitems" className="mt-4">
          <ChildItemsTab workItemId={id} slug={slug} />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
