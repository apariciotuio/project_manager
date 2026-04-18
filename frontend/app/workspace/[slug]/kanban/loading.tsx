import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { PageContainer } from '@/components/layout/page-container';

export default function KanbanLoading() {
  return (
    <PageContainer variant="wide">
      <SkeletonLoader variant="card" count={4} />
    </PageContainer>
  );
}
