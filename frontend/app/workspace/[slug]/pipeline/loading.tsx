import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { PageContainer } from '@/components/layout/page-container';

export default function PipelineLoading() {
  return (
    <PageContainer variant="wide">
      <SkeletonLoader variant="card" count={5} />
    </PageContainer>
  );
}
